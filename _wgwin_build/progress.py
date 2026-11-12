# -*- coding: utf-8 -*-
"""撰稿进度 / 缺口快检：不因缺文件中断，输出每篇的严格中文字数与要素统计。"""
import os
import re
import glob
import json

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')
EXPECT = {'01': 4, '02': 5, '03': 6, '04': 8,
          '05': 9, '06': 12, '07': 12, '08': 6}


def strict_cjk(text):
    out, i = [], 0
    lines = text.splitlines()
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith(':::figure'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(':::'):
                i += 1
            i += 1
            continue
        if s.startswith('```'):
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
    total = 0
    gaps = []
    for code, expect in EXPECT.items():
        p = os.path.join(DRAFTS, code + '.txt')
        if not os.path.exists(p):
            print('%s  文件缺失（0/%d 篇）' % (code, expect))
            gaps.append('%s 全册' % code)
            continue
        s = open(p, encoding='utf-8').read()
        parts = re.split(r'(?=^## \d{2}-\d{2} )', s, flags=re.M)
        heads = [x for x in parts if re.match(r'^## \d{2}-\d{2}', x)]
        ids = [re.match(r'^## (\d{2}-\d{2})', x).group(1) for x in heads]
        want = ['%s-%02d' % (code, i) for i in range(1, expect + 1)]
        print('%s  篇=%2d/%d  图=%2d  哨兵=%d  编号=%s' %
              (code, len(ids), expect, len(re.findall(r'^:::figure', s, re.M)),
               s.count('<!--NEXT-->'), 'OK' if ids == want else 'CHECK ' + ','.join(ids)))
        for sid, body in zip(ids, heads):
            cjk = strict_cjk(body)
            figs = len(re.findall(r'^:::figure', body, re.M))
            tabs = len(re.findall(r'^\|.+\|\s*$', body, re.M))
            codes = len([l for l in body.splitlines()
                         if l.strip().startswith('```') and l.strip() != '```'])
            total += cjk
            mark = '' if cjk >= 3000 and figs >= 1 else '  <== 待补'
            print('   %s  汉字=%4d 图=%d 表行=%2d 代码块=%d%s' % (sid, cjk, figs, tabs, codes, mark))
            if cjk < 3000:
                gaps.append('%s 字数 %d' % (sid, cjk))
        missing = [x for x in want if x not in ids]
        if missing:
            gaps.append('%s 缺篇 %s' % (code, ','.join(missing)))
        if s.count('<!--NEXT-->'):
            gaps.append('%s 哨兵残留' % code)
    print('\n严格中文合计 %d 字｜缺口 %d 项' % (total, len(gaps)))
    if gaps:
        print('缺口:', '; '.join(gaps[:40]))


if __name__ == '__main__':
    main()
