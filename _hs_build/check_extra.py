# -*- coding: utf-8 -*-
"""补充审阅：超长表格单元格定位、图/表正文呼应、总纲结构。"""
import os
import re
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')
FENCE = '`' * 3


def split_row(line):
    s = line.strip()
    s = re.sub(r'^\|', '', s)
    s = re.sub(r'(?<!\\)\|$', '', s)
    return [c.strip() for c in re.split(r'(?<!\\)\|', s)]


print('=== 超长表格单元格（>92 字符）===')
cnt = 0
for p in sorted(glob.glob(os.path.join(DRAFTS, '0[1-8].txt'))):
    ls = open(p, encoding='utf-8').read().splitlines()
    for i, l in enumerate(ls):
        if l.strip().startswith('|'):
            for c in split_row(l):
                if len(c) > 92:
                    cnt += 1
                    print(' %s L%-5d len=%3d | %s' % (os.path.basename(p), i + 1, len(c), c[:170]))
                    break
print('合计', cnt)

print('\n=== 图块缺前置引导 ===')
fig_iso = []
fig_total = 0
for p in sorted(glob.glob(os.path.join(DRAFTS, '0[1-8].txt'))):
    ls = open(p, encoding='utf-8').read().splitlines()
    for i, l in enumerate(ls):
        if l.strip().startswith(':::figure'):
            fig_total += 1
            ctx = ' '.join(ls[max(0, i - 4):i])
            if not re.search(r'图|如下|下图|示意|流程|关系|架构|链路|布局|拓扑', ctx):
                fig_iso.append((os.path.basename(p), i + 1, l.strip()[:80]))
print('数量', len(fig_iso), '/', fig_total)
for x in fig_iso[:20]:
    print(' ', x)

print('\n=== 表格缺前置说明（仅列前 20）===')
tab_iso = []
tab_total = 0
for p in sorted(glob.glob(os.path.join(DRAFTS, '0[1-8].txt'))):
    ls = open(p, encoding='utf-8').read().splitlines()
    for i, l in enumerate(ls):
        # 只认「下一行是纯分隔行」的表头，避免把含连字符的数据行误判成表头
        nxt = ls[i + 1].strip() if i + 1 < len(ls) else ''
        is_sep = nxt.startswith('|') and re.fullmatch(r'[|\-: ]+', nxt) is not None
        if l.strip().startswith('|') and is_sep:
            tab_total += 1
            ctx = ' '.join(ls[max(0, i - 3):i])
            if not re.search(r'表|如下|对照|清单|汇总|一览|速查|列表|说明|字段|参数|命令', ctx):
                tab_iso.append((os.path.basename(p), i + 1, l.strip()[:80]))
print('数量', len(tab_iso), '/', tab_total)
for x in tab_iso[:20]:
    print(' ', x)

print('\n=== 00.txt 交付版结构 ===')
s = open(os.path.join(DRAFTS, '00.txt'), encoding='utf-8').read()
ls = s.splitlines()
print('行数', len(ls), '字符', len(s))
print('二级标题', [l for l in ls if l.startswith('## ')])
print('残留 .md =', s.count('.md'), ' / 残留 mermaid 描述行 =',
      sum(1 for l in ls if 'mermaid' in l and not l.strip().startswith('```')))
print('代码块开始行', [l.strip() for l in ls if l.strip().startswith(FENCE) and l.strip() != FENCE])
print('表格行数', sum(1 for l in ls if l.strip().startswith('|')))
