# -*- coding: utf-8 -*-
"""最终校验：篇数 / 编号 / 字数 / 图形结构 / 位图检查（不依赖 Word）"""
import os
import re
import zipfile

BASE = r'C:\Users\mythos\SynologyDrive\技术学习'
BUILD = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BUILD, 'drafts')
OUT = os.path.join(BASE, 'OpenVPN技术资料')

EXPECT = {'01': 4, '02': 5, '03': 6, '04': 8,
          '05': 9, '06': 12, '07': 12, '08': 6}


def check_drafts():
    rows = []
    for code, expect in EXPECT.items():
        p = os.path.join(DRAFTS, code + '.txt')
        if not os.path.exists(p):
            rows.append((code, 'MISSING', 0, 0, 0, '内容源缺失'))
            continue
        s = open(p, encoding='utf-8').read()
        heads = re.findall(r'^##\s+(\d{2}-\d{2})\s+(.+)$', s, re.M)
        ids = [h[0] for h in heads]
        figs = len(re.findall(r'^:::figure', s, re.M))
        sentinel = '<!--NEXT-->' in s
        chars = len(re.sub(r'\s', '', s))
        ok = (len(ids) == expect and ids == [f'{code}-{i:02d}' for i in range(1, expect + 1)])
        status = 'OK' if ok and not sentinel else 'CHECK'
        note = []
        if not ok:
            note.append(f'篇数/编号异常: {len(ids)}/{expect}')
        if sentinel:
            note.append('哨兵残留')
        rows.append((code, status, len(ids), figs, chars, '; '.join(note)))
    return rows


def check_docx():
    rows = []
    for code in EXPECT:
        matches = [f for f in os.listdir(OUT) if f.startswith(code + '_') and f.endswith('.docx')]
        if not matches:
            rows.append((code, 'MISSING', 0, 0, 0, 0))
            continue
        p = os.path.join(OUT, matches[0])
        x = zipfile.ZipFile(p).read('word/document.xml').decode('utf-8')
        groups = x.count('<wpg:wgp>')
        shapes = x.count('<wps:wsp>')
        blips = x.count('<a:blip') + x.count('<v:imagedata')
        tables = x.count('<w:tbl>')
        rows.append((code, matches[0], groups, shapes, tables, blips))
    return rows


def main():
    print('=== 内容源校验（篇数 / 编号 / 图 / 字数）===')
    dr = check_drafts()
    all_ok = True
    for r in dr:
        print(f'{r[0]}  {r[1]:7s} 篇数={r[2]:2d}  图={r[3]:2d}  非空白字符={r[4]:6d}  {r[5]}')
        if r[1] != 'OK':
            all_ok = False
    print(f'内容源合计: {sum(r[2] for r in dr)} 篇, {sum(r[3] for r in dr)} 张图, '
          f'{sum(r[4] for r in dr)} 字符')

    print('\n=== DOCX 结构校验（原生形状 / 位图）===')
    xr = check_docx()
    for c, name, g, sh, tb, bl in xr:
        print(f'{c}  {str(name)[:38]:38s} 形状组={g:2d} 子形状={sh:3d} 表格={tb:2d} 位图={bl}')
        if bl:
            all_ok = False
    figs_dir = os.path.join(OUT, 'figures')
    drawios = [f for f in os.listdir(figs_dir) if f.endswith('.drawio')] if os.path.isdir(figs_dir) else []
    mds = [f for f in os.listdir(OUT) if f.endswith('.md')]
    print(f'\ndrawio 源文件: {len(drawios)} 个')
    print(f'交付目录 .md 文件: {len(mds)} 个（应为 0）')
    if mds:
        all_ok = False
    print('\n结论:', 'PASS' if all_ok else '需检查以上标记项')


if __name__ == '__main__':
    main()
