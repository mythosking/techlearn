# -*- coding: utf-8 -*-
"""四套资料交叉审计 v2：内容完整性 / 格式一致性 / 编码正确性

相比 v1 的改进：
- 代码块、图块、表格行先做行级分类，标题/引用/占位词检查只在叙述行上做
- 表格列数按「连续表格块」逐表校验，不再把同篇多张表混算
- 图节点宽度按 <br/> 分行计算
- 代码块内全角标点只对「非注释行 + 编程/配置语言」判定
- 占位词去掉 XXX/TODO 等源码里合法出现的字样
"""
import os
import re
import sys
import json
import zipfile
import hashlib
import xml.etree.ElementTree as ET

BASE = r'C:\Users\mythos\SynologyDrive\技术学习'

SETS = [
    ('VPP', '_vpp_build', 'VPP技术资料'),
    ('DPDK', '_dpdk_build', 'DPDK技术资料'),
    ('OpenVPN', '_openvpn_build', 'OpenVPN技术资料'),
    ('WGWin', '_wgwin_build', 'wireguard-windows技术资料'),
]

PLACEHOLDERS = ['（略）', '(略)', '（待补充）', '待补充', '（同上）', '省略若干', '此处省略',
                '此处不再赘述', '不再展开赘述']
MOJIBAKE = ['锟斤拷', '烫烫烫', '屯屯屯', 'ï¿½', 'â€', '浣犲', '鍜', '鐨']
CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
CODE_LANGS = {'go', 'c', 'cpp', 'python', 'py', 'json', 'yaml', 'yml', 'conf', 'ini',
              'bash', 'sh', 'powershell', 'ps1', 'xml', 'rust', 'java', 'makefile'}
FWH = '，。；：（）【】、“”‘’！？'


def han(s):
    return sum(1 for c in s if '\u4e00' <= c <= '\u9fff')


def classify(lines):
    """返回每行的类别: n=叙述 c=代码 f=图 t=表格 h=标题 b=空"""
    cls = []
    in_code, in_fig, fence = False, False, ''
    for ln in lines:
        st = ln.strip()
        if in_code:
            cls.append('c')
            if st.startswith('```'):
                in_code = False
            continue
        if in_fig:
            cls.append('f')
            if st == ':::':
                in_fig = False
            continue
        if st.startswith('```'):
            in_code = True
            fence = st[3:].strip().lower()
            cls.append('c')
            continue
        if st.startswith(':::figure'):
            in_fig = True
            cls.append('f')
            continue
        if st.startswith('|'):
            cls.append('t')
            continue
        if st.startswith('#'):
            cls.append('h')
            continue
        if not st:
            cls.append('b')
            continue
        cls.append('n')
    return cls


def audit_draft(path, vol):
    raw = open(path, 'rb').read()
    issues = []
    add = lambda kind, d: issues.append({'kind': kind, 'detail': d})
    if raw.startswith(b'\xef\xbb\xbf'):
        add('enc', 'UTF-8 BOM 存在')
    s = raw.decode('utf-8', errors='replace')
    if '\ufffd' in s:
        add('enc', f'U+FFFD x{s.count(chr(0xFFFD))}')
    for m in MOJIBAKE:
        if m in s:
            add('enc', f'乱码串 `{m}` x{s.count(m)}')
    for ch, nm in [('\u00a0', 'NBSP'), ('\u200b', 'ZWSP'), ('\u200c', 'ZWNJ'),
                   ('\u200d', 'ZWJ'), ('\ufeff', 'BOM字符')]:
        if s.count(ch):
            add('enc', f'{nm} x{s.count(ch)}')
    if s.count('\r\n') and s.count('\n') > s.count('\r\n'):
        add('enc', f'换行混用（CRLF {s.count(chr(13)+chr(10))} / LF {s.count(chr(10))-s.count(chr(13)+chr(10))}）')
    if CTRL.search(s):
        add('enc', f'控制字符 {len(CTRL.findall(s))} 处')

    lines = s.split('\n')
    cls = classify(lines)

    # ---------- 结构 ----------
    if not lines[0].startswith('# '):
        add('struct', '首行不是 `# 标题`')
    h1 = [i + 1 for i, (l, c) in enumerate(zip(lines, cls)) if c == 'h' and l.startswith('# ')]
    if len(h1) != 1:
        add('struct', f'一级标题 {len(h1)} 个（应为 1）')

    arts, cur = [], None
    for i, (l, c) in enumerate(zip(lines, cls)):
        m = re.match(r'^## (\d\d)-(\d\d)\s+(.*\S)\s*$', l) if c == 'h' else None
        if m:
            if cur:
                arts.append(cur)
            cur = [f'{m.group(1)}-{m.group(2)}', m.group(3), i + 1, []]
        elif cur is not None:
            cur[3].append((i + 1, l, c))
    if cur:
        arts.append(cur)

    nums = [a[0] for a in arts]
    exp = [f'{vol}-{i:02d}' for i in range(1, len(nums) + 1)]
    if nums != exp:
        miss = [x for x in exp if x not in nums]
        add('struct', f'篇号不连续（{len(nums)} 篇），缺 {miss[:6]}')

    fig_ids, stats = [], []
    for aid, title, lno, body in arts:
        text = '\n'.join(l for _, l, _ in body)
        narr = '\n'.join(l for _, l, c in body if c == 'n')
        hz = han(narr)
        h3 = [l for _, l, c in body if c == 'h' and l.startswith('### ')]
        st = {'id': aid, 'title': title, 'han': hz, 'sections': len(h3)}

        for p in PLACEHOLDERS:
            if p in narr:
                add('content', f'{aid} 叙述中出现占位词「{p}」')
        if hz < 3000:
            add('content', f'{aid} 严格中文字数 {hz} < 3000')
        if len(h3) < 5:
            add('struct', f'{aid} 小节数 {len(h3)} < 5')
        # 小节编号连续
        sn = [int(m.group(1)) for l in h3 if (m := re.match(r'^###\s*(\d+)[.、]', l))]
        if sn and sn != list(range(1, len(sn) + 1)):
            add('struct', f'{aid} 小节编号不连续 {sn}')

        # 代码块
        fences = [(i, l) for i, l, c in body if c == 'c' and l.strip().startswith('```')]
        if len(fences) % 2:
            add('format', f'{aid} 代码围栏未配对')
        in_code, lang, bare = False, '', 0
        for ln_no, l, c in body:
            stp = l.strip()
            if c == 'c' and stp.startswith('```'):
                if not in_code:
                    lang = stp[3:].strip().lower()
                    if not lang:
                        add('format', f'{aid} 代码块缺语言标注 L{ln_no}')
                in_code = not in_code
                continue
            if c != 'c':
                continue
            if re.fullmatch(r'[.…]{3,}', stp):
                bare += 1
            # 全角标点：非注释行 + 编程/配置文件语言
            if lang in CODE_LANGS:
                body_line = re.sub(r'^\s*(#|//|--|;).*$', '', l)
                if body_line.strip() and any(ch in body_line for ch in FWH):
                    add('format', f'{aid} 代码行含全角标点 L{ln_no} [{lang}]')
        if bare:
            add('content', f'{aid} 代码块内裸省略 {bare} 行')

        # 表格（按连续块）
        blocks, cur_t = [], []
        for ln_no, l, c in body:
            if c == 't':
                cur_t.append((ln_no, l))
            elif cur_t:
                blocks.append(cur_t)
                cur_t = []
        if cur_t:
            blocks.append(cur_t)
        if not blocks:
            add('content', f'{aid} 无表格')
        for b in blocks:
            widths = {}
            for ln_no, l in b:
                n = len(re.split(r'(?<!\\)\|', l.strip().strip('|')))
                widths.setdefault(n, []).append(ln_no)
            if len(widths) > 1:
                add('format', f'{aid} 表格列数不一致 L{b[0][0]}：'
                              f'{ {k: v[:3] for k, v in widths.items()} }')
            if len(b) < 3:
                add('format', f'{aid} 表格过短 L{b[0][0]}（{len(b)} 行）')
            for ln_no, l in b:
                over = [c for c in re.split(r'(?<!\\)\|', l.strip().strip('|')) if len(c) > 100]
                if over:
                    add('format', f'{aid} 单元格超长 L{ln_no}（{len(over[0])} 字符）')

        # 图
        figheads = [(ln_no, l) for ln_no, l, c in body if c == 'f' and l.strip().startswith(':::figure')]
        if not figheads:
            add('content', f'{aid} 无配图')
        for ln_no, head in figheads:
            f = dict(re.findall(r'(\w+)=([^|]+)', head))
            fid = (f.get('id') or '').strip()
            if not re.fullmatch(r'\d\d-\d\d-\d\d', fid):
                add('format', f'{aid} 图 id 异常 `{fid}` L{ln_no}')
            elif not fid.startswith(aid):
                add('format', f'{aid} 图 id 前缀不符 {fid}')
            else:
                fig_ids.append(fid)
            if not (f.get('name') or '').strip():
                add('format', f'{fid or aid} 缺 name')
            if (f.get('dir') or '').strip() not in ('TD', 'LR', 'TB', 'RL', 'BT'):
                add('format', f'{fid or aid} dir 异常 {f.get("dir")}')
        for m in re.finditer(r'^:::figure.*?\n(.*?)^:::\s*$', text, re.M | re.S):
            blk = m.group(0)
            nodes = re.findall(r'^node\s+(\S+)', blk, re.M)
            edges = re.findall(r'^edge\s+(\S+)\s*->\s*(\S+)', blk, re.M)
            fid = (re.search(r'id=(\S+)', blk.split('\n')[0]) or [None, '?'])[1]
            if len(nodes) > 10:
                add('format', f'{fid} 节点 {len(nodes)} > 10')
            if len(edges) > 12:
                add('format', f'{fid} 边 {len(edges)} > 12')
            linked = {x for e in edges for x in e}
            orphan = [n for n in nodes if n not in linked]
            if orphan:
                add('format', f'{fid} 孤立节点 {orphan}')
            for ln in blk.split('\n'):
                if ln.startswith('node '):
                    mm = re.search(r'node\s+\S+\s+"((?:[^"\\]|\\.)*)"', ln)
                    if mm:
                        for seg in mm.group(1).split('<br/>'):
                            wd = sum(2 if ord(ch) > 127 else 1 for ch in seg)
                            if wd > 40:
                                add('format', f'{fid} 节点单行过宽({wd}) {seg[:22]}')
            # 引导句：图块前最后一个非空叙述行应为句子
            idx = text.find(blk)
            prev = [x for x in text[:idx].split('\n') if x.strip()]
            if prev:
                p = prev[-1].strip()
                if p.startswith(('#', '|', ':::', '```')) or p.endswith('：'):
                    add('format', f'{fid} 图块前置引导句缺失/被标题截断')

        # 表格引导句
        for b in blocks:
            first = b[0][0]
            idx = text.find(b[0][1])
            prev = [x for x in text[:idx].split('\n') if x.strip()]
            if prev:
                p = prev[-1].strip()
                if p.startswith(('#', '|', ':::', '```')):
                    add('format', f'{aid} 表格缺引导句 L{first}')
        stats.append(st)

    # 图号引用
    refs = set(re.findall(r'图\s*(\d\d-\d\d-\d\d)', s))
    ghost = sorted(refs - set(fig_ids))
    if ghost:
        add('format', f'引用不存在的图号 {ghost[:8]}')
    if refs and len(refs) < len(fig_ids):
        add('style', f'{len(fig_ids)-len(refs)} 张图未被编号引用（正文可能用「下图」）')

    # 交叉引用（同册）
    for m in re.finditer(r'见\s*(\d\d)-(\d\d)', s):
        if m.group(1) == vol and m.group(0) not in all_ids(nums) if False else False:
            pass
    all_ids = set(nums)
    for m in re.finditer(r'(?:见|参见)\s*(\d\d)-(\d\d)', s):
        if m.group(1) == vol:
            t = f'{m.group(1)}-{m.group(2)}'
            if t not in all_ids:
                add('format', f'同册交叉引用失效 {t}')

    summary = {'volume': vol, 'articles': len(arts), 'figures': len(fig_ids),
               'han': sum(x['han'] for x in stats),
               'min_han': min((x['han'] for x in stats), default=0),
               'min_sec': min((x['sections'] for x in stats), default=0),
               'codes': sum(1 for c in cls if c == 'c') // 2,
               'tables': len(re.findall(r'^\|[-:\s|]+\|\s*$', s, re.M))}
    return issues, summary


def audit_docx(path):
    issues = []
    add = lambda k, d: issues.append({'kind': k, 'detail': d})
    try:
        z = zipfile.ZipFile(path)
        if z.testzip():
            add('enc', 'zip 条目损坏')
        xml = z.read('word/document.xml').decode('utf-8')
        ET.fromstring(xml.encode('utf-8'))
    except Exception as e:
        add('enc', f'无法解析 DOCX：{e}')
        return issues, {}
    if '<a:blip' in xml or '<v:imagedata' in xml:
        add('format', '存在位图引用')
    text = re.sub(r'<[^>]+>', '', xml)
    # 未渲染的 markdown 强调：排除 C 指针 `char **` 与输出里的星号分隔线
    for m in re.finditer(r'\*\*(?![*\s])', text):
        seg = text[m.start():m.start() + 60]
        if re.match(r'\*\*[^*\n]{1,40}\*\*', seg):
            add('format', f'未渲染粗体 ...{text[max(0,m.start()-12):m.start()+45]}...')
    for pat, nm in [(r'^#{2,}\s', '残留 ## 标题'), (r'\|-{3,}\|', '残留表格分隔符'),
                    (r'```', '残留代码围栏'), (r'<br/>', '残留 <br/>')]:
        if re.search(pat, text, re.M):
            add('format', f'{nm} x{len(re.findall(pat, text, re.M))}')
    if '\ufffd' in text:
        add('enc', f'U+FFFD x{text.count(chr(0xFFFD))}')
    for m in MOJIBAKE:
        if m in text:
            add('enc', f'乱码 `{m}` x{text.count(m)}')
    if CTRL.search(text):
        add('enc', '控制字符')
    sty = hashlib.md5(z.read('word/styles.xml')).hexdigest()[:10] if 'word/styles.xml' in z.namelist() else 'none'
    sect = re.search(r'<w:sectPr.*?</w:sectPr>', xml, re.S)
    sect_h = hashlib.md5(sect.group(0).encode()).hexdigest()[:8] if sect else 'none'
    return issues, {'groups': xml.count('<wpg:wgp'), 'tables': xml.count('<w:tbl>'),
                    'captions': len(re.findall(r'图\s*\d\d-\d\d-\d\d', text)),
                    'styles': sty, 'sect': sect_h, 'bytes': os.path.getsize(path)}


def main():
    verbose = '--verbose' in sys.argv
    report, total = {}, 0
    for name, bdir, ddir in SETS:
        dpath, outdir = os.path.join(BASE, bdir, 'drafts'), os.path.join(BASE, ddir)
        print(f'\n{"="*74}\n### {name}  ({ddir})\n{"="*74}')
        rep = {'drafts': {}, 'docx': {}, 'issues': []}
        vols = sorted(f[:-4] for f in os.listdir(dpath) if re.fullmatch(r'0[0-8]\.txt', f))
        agg = {'articles': 0, 'figures': 0, 'han': 0, 'codes': 0, 'tables': 0}
        for v in vols:
            iss, sm = audit_draft(os.path.join(dpath, v + '.txt'), v)
            rep['drafts'][v] = {'summary': sm, 'issues': iss}
            for k in agg:
                agg[k] += sm.get(k, 0)
            flag = 'OK ' if not iss else f'{len(iss):2d}项'
            print(f'  {v}  {flag} 篇={sm["articles"]:2d} 图={sm["figures"]:2d} 表={sm["tables"]:2d} '
                  f'码={sm["codes"]:3d} 汉字={sm["han"]:6d} 最少篇={sm["min_han"]:4d} 最少节={sm["min_sec"]}')
            for it in iss:
                rep['issues'].append({'vol': v, **it})
            total += len(iss)
        print(f'  --- 小计 {agg["articles"]} 篇 / {agg["figures"]} 图 / {agg["tables"]} 表 / '
              f'{agg["codes"]} 码块 / {agg["han"]} 汉字')

        styles, sects = set(), set()
        for f in sorted(x for x in os.listdir(outdir) if x.endswith('.docx')):
            iss, dm = audit_docx(os.path.join(outdir, f))
            rep['docx'][f] = {'summary': dm, 'issues': iss}
            if dm:
                styles.add(dm['styles'])
                sects.add(dm['sect'])
                print(f'  {f[:32]:34s} 组={dm["groups"]:2d} 表={dm["tables"]:2d} 图题={dm["captions"]:2d} '
                      f'样式={dm["styles"]} 版式={dm["sect"]}')
            for it in iss:
                rep['issues'].append({'vol': 'docx:' + f, **it})
            total += len(iss)
        if len(styles) > 1:
            rep['issues'].append({'vol': 'docx', 'kind': 'format', 'detail': f'样式不统一 {sorted(styles)}'})
        if len(sects) > 1:
            rep['issues'].append({'vol': 'docx', 'kind': 'format', 'detail': f'页面设置不统一 {sorted(sects)}'})
        report[name] = rep
        print(f'  >>> {name} 问题 {len(rep["issues"])}')

    print(f'\n{"="*74}\n### 跨套样式/版式')
    for n, r in report.items():
        print(f'  {n}: 样式 {sorted({d["summary"].get("styles") for d in r["docx"].values() if d["summary"]})} '
              f'版式 {sorted({d["summary"].get("sect") for d in r["docx"].values() if d["summary"]})}')

    kinds = {}
    for n, r in report.items():
        for it in r['issues']:
            kinds.setdefault(it['kind'], []).append(f'{n}/{it["vol"]}: {it["detail"]}')
    print(f'\n{"="*74}\n### 问题汇总')
    for k, v in sorted(kinds.items()):
        print(f'  {k}: {len(v)}')
    print(f'  总计 {total} 项  ->  _audit_all/audit_all_report.json')
    if verbose:
        for k, v in sorted(kinds.items()):
            print(f'\n--- {k} ---')
            for x in v[:100]:
                print('   ', x)
    with open(os.path.join(BASE, '_audit_all', 'audit_all_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
