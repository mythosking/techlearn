# -*- coding: utf-8 -*-
"""DPDK 资料内容源审阅脚本：逐篇审计图 / 表 / 示例 / 结构，输出机器可读报告。"""
import os
import re
import sys
import json
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
from vpp_figdsl import parse_dsl, auto_layout, TONES

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')

TONES_OK = TONES
PLACEHOLDER = re.compile(r'（略）|待补充|TODO|同上|参见前文不再赘述|<占位|XXXXX|xxxxx')
DISPLAY = lambda s: sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def split_sections(src):
    """按 ## 篇章切分，返回 [(id, title, lineno_start, lineno_end, text)]"""
    lines = src.splitlines()
    marks = [(i, m.group(1), m.group(2).strip())
             for i, l in enumerate(lines)
             for m in [re.match(r'^##\s+(\d{2}-\d{2})\s+(.+)$', l)] if m]
    out = []
    for k, (i, sid, title) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.append((sid, title, i + 1, end, '\n'.join(lines[i:end])))
    return out


def scan_figures(text, base_line):
    """返回 (figs, issues)，figs 含解析后的尺寸信息"""
    figs, issues = [], []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith(':::figure'):
            i += 1
            continue
        start = i
        buf = [lines[i].strip()]
        i += 1
        while i < len(lines) and not lines[i].strip().startswith(':::'):
            buf.append(lines[i])
            i += 1
        closed = i < len(lines)
        if closed:
            i += 1
        body = '\n'.join(buf)
        ln = base_line + start
        head = buf[0]
        mid = re.search(r'id\s*=\s*([^\s|]+)', head)
        fid = mid.group(1) if mid else '(缺 id)'
        nname = re.search(r'name\s*=\s*([^|]+)', head)
        fname = nname.group(1).strip() if nname else '(缺 name)'
        if not closed:
            issues.append((ln, fid, '图块未闭合'))
        if not mid:
            issues.append((ln, fid, '缺 id'))
        if not nname:
            issues.append((ln, fid, '缺 name'))
        ids, node_texts, edges = [], [], []
        for raw in buf[1:]:
            s = raw.strip()
            m = re.match(r'node\s+(\S+)\s+"([^"]*)"(?:\s+(\w+))?', s)
            if m:
                ids.append(m.group(1))
                node_texts.append(m.group(2))
                if m.group(3) and m.group(3) not in TONES_OK:
                    issues.append((ln, fid, '非法色调: ' + m.group(3)))
                continue
            m = re.match(r'edge\s+(\S+)\s*->\s*(\S+)', s)
            if m:
                edges.append((m.group(1), m.group(2)))
                continue
            if s:
                issues.append((ln, fid, '无法解析的图行: ' + s[:40]))
        dup = [x for x in set(ids) if ids.count(x) > 1]
        if dup:
            issues.append((ln, fid, 'node id 重复: ' + ','.join(dup)))
        for a, b in edges:
            if a not in ids or b not in ids:
                issues.append((ln, fid, 'edge 引用不存在节点: %s->%s' % (a, b)))
        linked = set(x for e in edges for x in e)
        for nid, t in zip(ids, node_texts):
            if nid not in linked and len(ids) > 1:
                issues.append((ln, fid, '孤立节点: ' + nid))
        for t in node_texts:
            # <br/> 是合法换行标记，按最长单行判断可读性
            tl = re.sub(r'<br\s*/?>', '\n', t, flags=re.I)
            longest = max((DISPLAY(x) for x in tl.split('\n')), default=0)
            if longest > 38:
                issues.append((ln, fid, '节点单行过长(%d宽): %s'
                               % (longest, tl.replace('\n', ' / ')[:40])))
            if not t.strip():
                issues.append((ln, fid, '空节点文字'))
        if len(ids) < 3:
            issues.append((ln, fid, '节点过少: %d' % len(ids)))
        if len(ids) > 12:
            issues.append((ln, fid, '节点过多: %d（易被压缩）' % len(ids)))
        fig = parse_dsl(body, fid)
        scale = min(1.0, 600.0 / fig['width'], 780.0 / fig['height'])
        figs.append({'id': fid, 'name': fname, 'line': ln,
                     'nodes': len(ids), 'edges': len(edges),
                     'w': fig['width'], 'h': fig['height'],
                     'scale': round(scale, 3)})
        # 超出版心/单页时由 normalize_fig 等比缩放（字号同步），属设计内行为
        if fig['width'] > 600:
            issues.append((ln, fid, '超宽图 W=%d（布局阶段应已折行）' % fig['width']))
        if scale < 0.72:
            issues.append((ln, fid, '缩放系数 %.2f 偏低，字号将降至 %.1fpt'
                           % (scale, max(7.0, 10 * max(0.7, scale)))))
    return figs, issues


def split_row(line):
    """与 md2docx._split_table_row 保持一致：转义的管道符不是列分隔"""
    s = line.strip()
    s = re.sub(r'^\|', '', s)
    s = re.sub(r'(?<!\\)\|$', '', s)
    return [c.strip() for c in re.split(r'(?<!\\)\|', s)]


def scan_tables(text, base_line):
    """模拟 md2docx 的表格识别，找出列数不一致 / 未转义管道符 / 未被识别的表格"""
    lines = text.splitlines()
    tabs, issues = [], []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        is_sep = bool(re.match(r'^\s*\|?[\s:\-\|]+\|[\s:\-\|]*$', nxt)) and '-' in nxt
        if s.startswith('|') and is_sep:
            ln = base_line + i
            hdr = split_row(s)
            cols = len(hdr)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                r = split_row(lines[i])
                rows.append(r)
                if len(r) != cols:
                    issues.append((ln, 'T', '行列数不一致 期望%d 实得%d: %s'
                                   % (cols, len(r), lines[i].strip()[:70])))
                i += 1
            empty = sum(1 for r in rows for c in r if not c)
            longc = max([len(c) for r in rows + [hdr] for c in r] or [0])
            tabs.append({'line': ln, 'cols': cols, 'rows': len(rows),
                         'empty': empty, 'maxcell': longc})
            if cols > 8:
                issues.append((ln, 'T', '列数过多 %d（版心挤压）' % cols))
            if empty:
                issues.append((ln, 'T', '空单元格 %d 个' % empty))
            if longc > 90:
                issues.append((ln, 'T', '超长单元格 %d 字符' % longc))
            if len(rows) == 0:
                issues.append((ln, 'T', '空表（仅表头）'))
            # 未转义管道符：单元格内出现 shell 管道，会被当成列分隔
            for r in rows[:3]:
                if len(r) > cols:
                    break
            continue
        if s.startswith('|') and not is_sep and re.search(r'\|.*\|', s):
            # 疑似表格但未紧跟分隔行
            issues.append((base_line + i, 'T', '疑似表格未被识别（下一行不是分隔行）: ' + s[:60]))
        i += 1
    return tabs, issues


def scan_code(text, base_line):
    lines = text.splitlines()
    blocks, issues = [], []
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith('```'):
            i += 1
            continue
        ln = base_line + i
        lang = lines[i].strip()[3:].strip()
        i += 1
        buf = []
        closed = False
        while i < len(lines):
            if lines[i].strip().startswith('```'):
                closed = True
                i += 1
                break
            buf.append(lines[i])
            i += 1
        body = '\n'.join(buf)
        if not closed:
            issues.append((ln, 'C', '代码块未闭合'))
        if not lang:
            issues.append((ln, 'C', '代码块缺语言标注'))
        if not body.strip():
            issues.append((ln, 'C', '空代码块'))
        m = PLACEHOLDER.search(body)
        if m:
            issues.append((ln, 'C', '示例含占位词: ' + m.group(0)))
        if re.search(r'^\s*(#|\$)?\s*(TODO|…|\.\.\.)\s*$', body, re.M):
            issues.append((ln, 'C', '示例含省略占位行'))
        # 未转义竖线在表格外的代码块里无害
        blocks.append({'line': ln, 'lang': lang, 'lines': len(buf),
                       'chars': len(body), 'has_output': bool(re.search(
                           r'^\s*(#|//|\*|\s*(Interface|Name|Idx|State|Counter|MTU|vpp#|\S+\s+\d+\s+\d+))',
                           body, re.M))})
    return blocks, issues


def strict_cjk(text):
    """排除图块 / 代码块 / 表格行后统计 CJK"""
    out, skip = [], False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith(':::figure'):
            while i < len(lines) and not lines[i].strip().startswith(':::'):
                i += 1
            i += 1
            continue
        if s.startswith('```'):
            lang = s[3:]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1
            continue
        if s.startswith('|'):
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return len(re.findall(r'[\u4e00-\u9fff]', '\n'.join(out)))


def main():
    all_sections, all_issues = [], []
    known = set()
    for code in ['01', '02', '03', '04', '05', '06', '07', '08']:
        p = os.path.join(DRAFTS, code + '.txt')
        src = open(p, encoding='utf-8').read()
        secs = split_sections(src)
        known |= set(re.findall(r'^##\s+(\d{2}-\d{2})', src, re.M))
        for sid, title, ls, le, text in secs:
            figs, fi = scan_figures(text, ls)
            tabs, ti = scan_tables(text, ls)
            codes, ci = scan_code(text, ls)
            h3 = re.findall(r'^###\s+(\d+)\.', text, re.M)
            iss = [(code, sid, *x) for x in fi + ti + ci]
            seq_ok = h3 == [str(i) for i in range(1, len(h3) + 1)]
            if not seq_ok:
                iss.append((code, sid, ls, 'S', '小节编号不连续: ' + ','.join(h3)))
            if not figs:
                iss.append((code, sid, ls, 'F', '本篇无配图'))
            if not tabs:
                iss.append((code, sid, ls, 'T', '本篇无表格'))
            if not codes:
                iss.append((code, sid, ls, 'C', '本篇无代码/命令示例'))
            elif len(codes) < 2:
                iss.append((code, sid, ls, 'C', '示例偏少: %d 个代码块' % len(codes)))
            all_issues += iss
            all_sections.append({
                'doc': code, 'id': sid, 'title': title, 'lines': [ls, le],
                'cjk': strict_cjk(text), 'figures': figs, 'tables': tabs, 'codes': codes,
                'h3': len(h3), 'issues': len(iss),
            })
    # 交叉引用是否指向真实篇号
    xref_issues = []
    for code in ['01', '02', '03', '04', '05', '06', '07', '08']:
        src = open(os.path.join(DRAFTS, code + '.txt'), encoding='utf-8').read()
        for m in re.finditer(r'\b(0[1-8]-\d{2})\b', src):
            if m.group(1) not in known:
                xref_issues.append((code, m.group(1)))
    # 输出
    print('=== 逐篇总览（篇号 字数 图 表 代码 问题数）===')
    for s in all_sections:
        flag = '' if s['issues'] == 0 else '  <== %d' % s['issues']
        print('%s %-4s 字=%4d 图=%d 表=%2d 示例=%2d%s'
              % (s['doc'], s['id'], s['cjk'], len(s['figures']),
                 len(s['tables']), len(s['codes']), flag))
    print('\n=== 图尺寸问题（缩放系数 < 0.85 会被压缩）===')
    wide = [f for s in all_sections for f in s['figures'] if f['scale'] < 0.85]
    for f in sorted(wide, key=lambda x: x['scale'])[:40]:
        print('  %-14s W=%4d 系数=%.2f 节点=%2d  %s' % (f['id'], f['w'], f['scale'], f['nodes'], f['name'][:28]))
    print('  超宽图合计: %d / %d' % (len(wide), sum(len(s['figures']) for s in all_sections)))
    print('\n=== 问题分类统计 ===')
    from collections import Counter
    cat = Counter(x[3] for x in all_issues)
    print(' ', dict(cat), ' 合计', len(all_issues))
    print('\n=== 问题明细（前 160 条）===')
    for x in all_issues[:160]:
        print('  %s/%s L%-5s [%s] %s' % (x[0], x[1], x[2], x[3], x[4]))
    print('\n=== 交叉引用异常 ===')
    print(' ', len(xref_issues), '处', xref_issues[:20])
    print('\n=== 汇总 ===')
    print(' 篇数=%d 图=%d 表=%d 代码块=%d 严格中文字数=%d'
          % (len(all_sections), sum(len(s['figures']) for s in all_sections),
             sum(len(s['tables']) for s in all_sections),
             sum(len(s['codes']) for s in all_sections),
             sum(s['cjk'] for s in all_sections)))
    print(' 无图篇=%d 无表篇=%d 无示例篇=%d'
          % (sum(1 for s in all_sections if not s['figures']),
             sum(1 for s in all_sections if not s['tables']),
             sum(1 for s in all_sections if not s['codes'])))
    with open(os.path.join(BASE, 'audit_report.json'), 'w', encoding='utf-8') as f:
        json.dump({'sections': all_sections, 'issues': all_issues,
                   'xref_bad': xref_issues}, f, ensure_ascii=False, indent=1)
    print(' 报告已写入 audit_report.json')


if __name__ == '__main__':
    main()
