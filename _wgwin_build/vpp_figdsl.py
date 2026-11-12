# -*- coding: utf-8 -*-
"""
图描述 -> 可编辑图形定义（带自动分层布局）

支持两种输入：
1) figure DSL（推荐，给撰稿用）
   :::figure id=06-02-01 | name=图节点处理图 | dir=TD
   node n1 "dpdk-input" blue
   node n2 "ethernet-input" teal
   edge n1 -> n2 "批量帧"
   edge n2 -> n1 dashed "回查"
   :::

2) mermaid flowchart（兼容存量 md）
   flowchart TD
     A["vppctl"] --> B["Binary API"]
     A -. "回查" .-> C["statseg"]
"""
import re
import unicodedata

TONES = {'blue', 'teal', 'amber', 'purple', 'gray', 'red', 'green', 'white'}

MAX_FIG_W = 600  # A4 版心约 16.2cm；布局阶段即保证不超宽，避免事后压缩字号


def _display_len(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def _node_width(label, fs=10):
    """按最长的一行计算宽度；多行节点（<br/> 已转成 \n）不再被拼成超宽节点"""
    lines = str(label).split('\n')
    n = max((_display_len(l) for l in lines), default=0)
    return max(112, min(260, int(n * fs * 0.62) + 34))


def _node_height(label):
    """多行节点按行数加高，保证文字不溢出形状"""
    return 44 + (len(str(label).split('\n')) - 1) * 15


def auto_layout(nodes, edges, direction='TD'):
    """最长路径分层 + 层内居中，输出带坐标的 fig dict 部件"""
    ids = [n['id'] for n in nodes]
    idx = {nid: i for i, nid in enumerate(ids)}
    succ = {nid: [] for nid in ids}
    pred = {nid: [] for nid in ids}
    for e in edges:
        a, b = e.get('from'), e.get('to')
        if a in idx and b in idx:
            succ[a].append(b)
            pred[b].append(a)

    # 最长路径分层。先用 Kahn 拓扑序剔除造成环的回边，保证层级可收敛。
    indeg = {nid: len(set(pred[nid])) for nid in ids}
    queue = [nid for nid in ids if indeg[nid] == 0]
    order = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for nxt in set(succ[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    in_order = set(order)
    # 环上节点按原顺序补入
    for nid in ids:
        if nid not in in_order:
            order.append(nid)
            in_order.add(nid)
    rank = {nid: i for i, nid in enumerate(order)}
    # 只保留「前驱排在前面」的边参与分层，回边仅用于画虚线
    fwd_pred = {nid: [] for nid in ids}
    for nid in ids:
        fwd_pred[nid] = [p for p in pred[nid] if rank[p] < rank[nid]]

    level = {nid: 0 for nid in ids}
    for nid in order:
        if fwd_pred[nid]:
            level[nid] = max(level[p] + 1 for p in fwd_pred[nid])

    # 仅「指向更早层级」的边算回边；同层边由实际 y 坐标决定画法
    for e in edges:
        a, b = e.get('from'), e.get('to')
        if a in idx and b in idx and level[b] < level[a]:
            e['_back'] = True

    layers = {}
    for nid in ids:
        layers.setdefault(level[nid], []).append(nid)

    NODE_H = 44
    NODE_GAP = 26
    ROW_GAP = 14
    LAYER_EXTRA = 36
    PAD = 22
    AVAIL = MAX_FIG_W - PAD * 2  # 556

    # 横向布局在层数较多时同样会超出版心，统一退化为纵向分层布局
    if direction != 'TD' and len(layers) * 190 + PAD * 2 > MAX_FIG_W:
        direction = 'TD'

    widths, heights = {}, {}
    for n in nodes:
        n['w'] = _node_width(n.get('text', ''), n.get('fs', 10))
        n['h'] = _node_height(n.get('text', ''))
        widths[n['id']] = n['w']
        heights[n['id']] = n['h']

    if direction == 'TD':
        # 同层节点过多时折成多行：图宽恒定 <= 版心，字号保持 10pt 不被压缩
        rows_by_level = {}
        for lv, ls in layers.items():
            rows, cur, cur_w = [], [], 0
            for nid in ls:
                add = widths[nid] + (NODE_GAP if cur else 0)
                if cur and cur_w + add > AVAIL:
                    rows.append(cur)
                    cur, cur_w = [nid], widths[nid]
                else:
                    cur.append(nid)
                    cur_w += add
            if cur:
                rows.append(cur)
            rows_by_level[lv] = rows

        pos, row_widths = {}, []
        cur_y = PAD
        for lv in sorted(layers):
            rows = rows_by_level[lv]
            for ri, r in enumerate(rows):
                rw = sum(widths[i] for i in r) + NODE_GAP * (len(r) - 1)
                rh = max(heights[i] for i in r)
                row_widths.append(rw)
                x = PAD + (AVAIL - rw) / 2
                for nid in r:
                    pos[nid] = (x, cur_y + (rh - heights[nid]) / 2)
                    x += widths[nid] + NODE_GAP
                cur_y += rh + (ROW_GAP if ri < len(rows) - 1 else LAYER_EXTRA)
        W = int(max(row_widths) + PAD * 2)
        H = int(cur_y - LAYER_EXTRA + PAD)
        for n in nodes:
            n['x'], n['y'] = pos[n['id']]
    else:
        W = len(layers) * 190 + PAD * 2
        max_layer = max(len(ls) for ls in layers.values())
        H = max_layer * (NODE_H + 24) + PAD * 2
        pos = {}
        for lv, ls in sorted(layers.items()):
            x = PAD + lv * 190
            total = sum(heights[i] for i in ls) + NODE_GAP * (len(ls) - 1)
            y = (H - total) / 2
            for nid in ls:
                pos[nid] = (x, y)
                y += heights[nid] + NODE_GAP
        for n in nodes:
            n['x'], n['y'] = pos[n['id']]

    by_id = {n['id']: n for n in nodes}
    out_edges = []
    for e in edges:
        a, b = e.get('from'), e.get('to')
        if a not in by_id or b not in by_id:
            continue
        na, nb = by_id[a], by_id[b]
        is_back = bool(e.get('_back'))
        if direction == 'TD':
            # 折行后按节点实际纵坐标决定连线方向，避免连线穿过中间行
            dy = nb['y'] - na['y']
            if is_back or dy < -8:  # 回边走右侧虚线路径
                x1, y1 = na['x'] + na['w'], na['y'] + na['h'] / 2
                x2, y2 = nb['x'] + nb['w'], nb['y'] + nb['h'] / 2
            elif dy > 8:  # 向下（含同层折行的下一行）
                x1, y1 = na['x'] + na['w'] / 2, na['y'] + na['h']
                x2, y2 = nb['x'] + nb['w'] / 2, nb['y']
            elif nb['x'] >= na['x']:
                x1, y1 = na['x'] + na['w'], na['y'] + na['h'] / 2
                x2, y2 = nb['x'], nb['y'] + nb['h'] / 2
            else:
                x1, y1 = na['x'], na['y'] + na['h'] / 2
                x2, y2 = nb['x'] + nb['w'], nb['y'] + nb['h'] / 2
        else:
            if level[b] > level[a]:
                x1, y1 = na['x'] + na['w'], na['y'] + na['h'] / 2
                x2, y2 = nb['x'], nb['y'] + nb['h'] / 2
            else:
                x1, y1 = na['x'] + na['w'] / 2, na['y'] + na['h']
                x2, y2 = nb['x'] + nb['w'] / 2, nb['y']
        ee = {'x1': round(x1, 1), 'y1': round(y1, 1),
              'x2': round(x2, 1), 'y2': round(y2, 1),
              'arrow': True, 'dashed': bool(e.get('dashed'))}
        if e.get('text'):
            ee['text'] = e['text']
            ee['label_w'] = max(70, min(150, _node_width(e['text'], 9)))
        out_edges.append(ee)

    return nodes, out_edges, int(W), int(H)


def parse_dsl(body, fig_id='FIG', name='Figure'):
    nodes, edges = [], []
    direction = 'TD'
    meta = re.search(r':::\s*figure\s+(.*)', body, re.I)
    if meta:
        s = meta.group(1)
        m = re.search(r'id\s*=\s*([^\s|]+)', s)
        if m:
            fig_id = m.group(1)
        m = re.search(r'name\s*=\s*([^|]+)', s)
        if m:
            name = m.group(1).strip()
        m = re.search(r'dir\s*=\s*(\w+)', s)
        if m:
            direction = m.group(1).upper()
    for line in body.splitlines():
        line = line.strip()
        m = re.match(r'node\s+(\S+)\s+"([^"]*)"(?:\s+(\w+))?', line)
        if m:
            tone = m.group(3) if m.group(3) in TONES else 'blue'
            # 内容源普遍用 <br/> 表示节点内换行，转成真实换行供形状文本框分行渲染
            label = re.sub(r'<br\s*/?>', '\n', m.group(2), flags=re.I)
            nodes.append({'id': m.group(1), 'text': label, 'tone': tone})
            continue
        m = re.match(r'edge\s+(\S+)\s*->\s*(\S+)(?:\s+(dashed))?\s*(?:"([^"]*)")?', line)
        if m:
            edges.append({'from': m.group(1), 'to': m.group(2),
                          'dashed': bool(m.group(3)), 'text': m.group(4) or ''})
            continue
        m = re.match(r'edge\s+(\S+)\s*->\s*(\S+)\s+"([^"]*)"', line)
        if m:
            edges.append({'from': m.group(1), 'to': m.group(2),
                          'dashed': False, 'text': m.group(3)})
    nodes, edges, W, H = auto_layout(nodes, edges, direction)
    return {'id': fig_id, 'name': name, 'width': W, 'height': H,
            'nodes': nodes, 'edges': edges}


def parse_mermaid(src, fig_id='FIG', name='Figure'):
    """解析 mermaid flowchart 常用子集，转换为同一 fig 结构"""
    nodes, edges = [], []
    seen = {}
    direction = 'TD'
    m = re.search(r'flowchart\s+(TD|TB|LR|RL|BT)', src, re.I)
    if m:
        direction = 'LR' if m.group(1).upper() in ('LR', 'RL') else 'TD'

    def get_node(token):
        token = token.strip()
        mm = re.match(r'([A-Za-z0-9_]+)\s*(?:\[|\(|\{)', token)
        nid = mm.group(1) if mm else re.sub(r'[^A-Za-z0-9_]', '_', token)[:24]
        label_m = re.search(r'[\[\(\{]\s*"([^"]*)"|\[([^\]]*)\]|\(([^)]*)\)', token)
        label = ''
        if label_m:
            label = next((g for g in label_m.groups() if g), '')
        label = re.sub(r'<br\s*/?>', '\n', label, flags=re.I)
        if nid not in seen:
            seen[nid] = True
            tone = 'purple' if any(k in label for k in ('API', '控制面', 'CLI', 'Honeycomb')) else 'blue'
            nodes.append({'id': nid, 'text': label or nid, 'tone': tone})
        return nid

    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith(('flowchart', 'graph ', 'subgraph', 'end', '%%', 'classDef', 'style')):
            continue
        # 虚线回查： A -. "label" .-> B
        m = re.match(r'(.+?)\s*-\.\s*(?:"([^"]*)")?\s*\.->\s*(.+)', line)
        if m:
            a, b = get_node(m.group(1)), get_node(m.group(3))
            edges.append({'from': a, 'to': b, 'dashed': True, 'text': m.group(2) or ''})
            continue
        # 实线： A --> B  或  A -- "label" --> B
        m = re.match(r'(.+?)\s*--\s*(?:"([^"]*)")?\s*-->\s*(.+)', line)
        if m:
            a, b = get_node(m.group(1)), get_node(m.group(3))
            edges.append({'from': a, 'to': b, 'dashed': False, 'text': m.group(2) or ''})
            continue
        m = re.match(r'(.+?)\s*-->\s*(?:"([^"]*)"\s*\|\s*)?(.+)', line)
        if m:
            a, b = get_node(m.group(1)), get_node(m.group(3))
            edges.append({'from': a, 'to': b, 'dashed': False, 'text': m.group(2) or ''})
            continue
    nodes, edges, W, H = auto_layout(nodes, edges, direction)
    return {'id': fig_id, 'name': name, 'width': W, 'height': H,
            'nodes': nodes, 'edges': edges}
