# -*- coding: utf-8 -*-
"""交付终检：篇号 / 图号 / drawio / DOCX 结构 / 图题引用 / 表格排版 / 目录洁净度。"""
import os
import re
import sys
import glob
import json
import zipfile
import collections
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vpp_docgen import EMU
import docx

BASE = r'C:\Users\mythos\SynologyDrive\技术学习'
BUILD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'Hyperscan技术资料')
FIGS = os.path.join(OUT, 'figures')
DRAFTS = os.path.join(BUILD, 'drafts')

EXPECT_SEC = {'01': 4, '02': 5, '03': 6, '04': 8,
              '05': 9, '06': 14, '07': 13, '08': 6}
LABELS = ('命令示例', '代码片段', '配置片段', '输出 / 文本示例', '目录结构', '数据片段', '示例 ·')

report = json.load(open(os.path.join(BUILD, 'build_report.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(BUILD, 'build_report.json')) else []
EXPECT_FIG = {x['code']: x.get('figures', 0) for x in report if x.get('status') == 'ok'}

fail = []


def section(title):
    print('\n=== %s ===' % title)


section('1. 内容源：篇号 / 图号 / 代码块')
sec_ids, fig_ids = [], []
for p in sorted(glob.glob(os.path.join(DRAFTS, '0[1-8].txt'))):
    s = open(p, encoding='utf-8').read()
    sec_ids += re.findall(r'^##\s+(\d{2}-\d{2})\s+', s, re.M)
    fig_ids += re.findall(r'^:::figure\s+id=([^\s|]+)', s, re.M)
    fence = '`' * 3
    starts = sum(1 for l in s.splitlines() if l.strip().startswith(fence) and l.strip() != fence)
    ends = sum(1 for l in s.splitlines() if l.strip() == fence)
    bare = sum(1 for l in s.splitlines() if l.strip() in ('...', '…'))
    ok = starts == ends and bare == 0 and '<!--NEXT-->' not in s
    print(' %s 篇=%2d 图=%2d 代码块=%2d/%2d 裸省略=%d %s'
          % (os.path.basename(p), len(re.findall(r'^##\s+\d{2}-\d{2}', s, re.M)),
             len(re.findall(r'^:::figure', s, re.M)), starts, ends, bare,
             'OK' if ok else 'CHECK'))
    if not ok:
        fail.append('%s 代码块/占位异常' % os.path.basename(p))
want_secs = sum(EXPECT_SEC.values())
print(' 篇号 %d 个（期望 %d，唯一 %d）｜图号 %d 个（唯一 %d）'
      % (len(sec_ids), want_secs, len(set(sec_ids)), len(fig_ids), len(set(fig_ids))))
if len(sec_ids) != want_secs or len(set(sec_ids)) != want_secs or len(fig_ids) != len(set(fig_ids)):
    fail.append('篇号/图号数量或唯一性异常')

section('2. draw.io 源文件')
ds = sorted(glob.glob(os.path.join(FIGS, '*.drawio')))
bad = []
br_count = 0
for d in ds:
    try:
        r = ET.parse(d).getroot()
        assert r.tag == 'mxfile' and r.find('.//mxGraphModel') is not None
        br_count += open(d, encoding='utf-8').read().count('&lt;br&gt;')
    except Exception as e:
        bad.append((os.path.basename(d), str(e)))
want_figs = sum(EXPECT_FIG.values())
print(' 总数 %d（期望 %d）｜解析失败 %d｜含换行节点 %d'
      % (len(ds), want_figs, len(bad), br_count))
for b in bad[:5]:
    print('  BAD', b)
if len(ds) != want_figs or bad:
    fail.append('drawio 数量或合法性异常')

section('3. DOCX 结构（原生形状 / 位图 / 表格排版 / 图题）')
tot = collections.Counter()
for code in sorted(EXPECT_FIG):
    m = [f for f in os.listdir(OUT) if f.startswith(code + '_') and f.endswith('.docx')]
    if not m:
        fail.append('%s DOCX 缺失' % code)
        continue
    p = os.path.join(OUT, m[0])
    x = zipfile.ZipFile(p).read('word/document.xml').decode('utf-8')
    groups = x.count('<wpg:wgp>')
    shapes = x.count('<wps:wsp>')
    blips = x.count('<a:blip') + x.count('<v:imagedata')
    tables = x.count('<w:tbl>')
    hdr_repeat = x.count('<w:tblHeader')
    cant_split = x.count('<w:cantSplit')
    labels = sum(x.count(l) for l in LABELS)
    extents = [(int(a), int(b)) for a, b in re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"', x)]
    max_h = max((b for a, b in extents), default=0) / EMU
    max_w = max((a for a, b in extents), default=0) / EMU
    ok = (groups == EXPECT_FIG[code] and blips == 0 and max_h <= 785 and max_w <= 605)
    print(' %s %-34s 组=%2d/%2d 子形状=%4d 表=%3d 表头重复=%3d 防拆行=%3d 示例标签=%3d 位图=%d 最大图=%dx%dpx %s'
          % (code, m[0][:34], groups, EXPECT_FIG[code], shapes, tables,
             hdr_repeat, cant_split, labels, blips, int(max_w), int(max_h),
             'OK' if ok else 'CHECK'))
    tot['groups'] += groups
    tot['shapes'] += shapes
    tot['tables'] += tables
    tot['labels'] += labels
    tot['hdr'] += hdr_repeat
    tot['cant'] += cant_split
    if not ok:
        fail.append('%s DOCX 结构异常' % code)
print(' 合计: 组=%d 子形状=%d 表格=%d 表头重复=%d 防拆行=%d 示例标签=%d'
      % (tot['groups'], tot['shapes'], tot['tables'], tot['hdr'], tot['cant'], tot['labels']))

section('4. 图题与正文引用一致')
cap_map = {}
for code in sorted(EXPECT_FIG):
    m = [f for f in os.listdir(OUT) if f.startswith(code + '_') and f.endswith('.docx')]
    d = docx.Document(os.path.join(OUT, m[0]))
    caps = [p.text for p in d.paragraphs
            if re.match(r'^图\s+\S+', p.text.strip())
            and p.text.strip().endswith('（可编辑 · 附 draw.io 源文件）')]
    cap_map[code] = caps
    print(' %s 图题 %2d 条，例：%s' % (code, len(caps), caps[0][:60] if caps else '-'))
allcaps = sum(cap_map.values(), [])
cap_ids = {re.match(r'^图\s+(\S+)', c).group(1) for c in allcaps}
missing = set(fig_ids) - cap_ids
extra = cap_ids - set(fig_ids) - {'00-01-01'}
print(' 图题总数 %d，唯一图号 %d，内容源图 id 未上图题 %d，多余图题 %d'
      % (len(allcaps), len(cap_ids), len(missing), len(extra)))
if missing or extra:
    fail.append('图题与内容源图 id 不一致')

section('5. 交付目录洁净度')
files = sorted(os.listdir(OUT))
print(' 顶层文件:', ', '.join(f for f in files if not os.path.isdir(os.path.join(OUT, f))))
mds = [f for f in files if f.endswith('.md')]
print(' .docx = %d ｜ .md = %d ｜ figures/*.drawio = %d'
      % (len([f for f in files if f.endswith('.docx')]), len(mds), len(ds)))
if mds:
    fail.append('交付目录仍有 .md 文件')

section('结论')
print(' ', 'PASS' if not fail else '需检查: ' + '; '.join(fail))
