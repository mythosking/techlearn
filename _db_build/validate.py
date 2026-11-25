# -*- coding: utf-8 -*-
"""校验数据库草稿：图节点/表格/码块/残留词。用法: python validate.py drafts/XXX.txt"""
import re, sys, unicodedata
sys.path.insert(0, '.')
import md2docx
from vpp_figdsl import parse_dsl, TONES

path = sys.argv[1]
src = open(path, encoding='utf-8').read()
lines = src.splitlines()
W = lambda s: sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)
issues = []
figs = []
for i, l in enumerate(lines):
    if l.strip().startswith(':::figure'):
        head = l.strip(); buf = [head]; j = i + 1
        while j < len(lines) and not lines[j].strip().startswith(':::'):
            buf.append(lines[j]); j += 1
        fid = re.search(r'id\s*=\s*([^\s|]+)', head).group(1)
        ids = []; txts = []; edges = []
        for raw in buf[1:]:
            s = raw.strip()
            m = re.match(r'node\s+(\S+)\s+"([^"]*)"(?:\s+(\w+))?', s)
            if m:
                ids.append(m.group(1)); txts.append(m.group(2))
                if m.group(3) and m.group(3) not in TONES:
                    issues.append((fid, 'bad tone ' + str(m.group(3))))
                continue
            m = re.match(r'edge\s+(\S+)\s*->\s*(\S+)', s)
            if m:
                edges.append((m.group(1), m.group(2))); continue
            if s:
                issues.append((fid, 'bad line ' + s[:40]))
        if not (3 <= len(ids) <= 12):
            issues.append((fid, 'nodes %d' % len(ids)))
        linked = {x for e in edges for x in e}
        for nid in ids:
            if nid not in linked:
                issues.append((fid, 'isolated ' + nid))
        for t in txts:
            mx = max((W(x) for x in re.sub(r'<br\s*/?>', '\n', t, flags=re.I).split('\n')), default=0)
            if mx > 38:
                issues.append((fid, 'width %d %s' % (mx, t.replace('\n', '/')[:40])))
        try:
            f = parse_dsl('\n'.join(buf), fid)
            figs.append((fid, len(ids), f['width'], f['height']))
        except Exception as e:
            issues.append((fid, 'parse fail ' + str(e)[:50]))

tabs = 0; maxcols = 0
for i, l in enumerate(lines[:-1]):
    if l.strip().startswith('|') and md2docx._is_table_sep(lines[i + 1]):
        tabs += 1
        n = len(md2docx._split_table_row(l.strip())); maxcols = max(maxcols, n); j = i + 2
        while j < len(lines) and lines[j].strip().startswith('|'):
            row = md2docx._split_table_row(lines[j].strip())
            if len(row) != n:
                issues.append(('TABLE L%d' % (j + 1), 'cols %d != %d' % (len(row), n)))
            if any(not c for c in row):
                issues.append(('TABLE L%d' % (j + 1), 'empty cell'))
            j += 1

fences = re.findall(r'^```(\w*)\n(.*?)^```', src, re.M | re.S)
for fid, body in fences:
    if not body.strip():
        issues.append(('CODE', 'empty fence ' + fid))
sentinels = ['TODO', '待补充', '同上', '（略）', 'ifferent', 'designing',
             'крупные', 'notorious', 'freely', 'silicon', 'programmable',
             'high-load', 'symmetric', '_table', 'requirements', 'bandwidth']
for kw in sentinels:
    for k, l in enumerate(lines):
        if kw in l and not l.strip().startswith('```'):
            issues.append(('L%d' % (k + 1), 'sentinel ' + kw))

print('章节', len([l for l in lines if l.startswith('## ')]),
      '图', len(figs), '表', tabs, '码块', len(fences), '最大列', maxcols)
for f in figs:
    print('  FIG', f)
print('问题', len(issues))
for x in issues[:80]:
    print(' ', x)
