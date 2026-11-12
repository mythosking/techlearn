# -*- coding: utf-8 -*-
"""按册打印待修问题清单（供逐册修订使用）

用法: python fixhint.py 07 [--full]
输出: 该册每篇的字数、缺引导句的图/表行号与上下文、超限图、可执行清单
"""
import re
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DRAFTS = os.path.join(ROOT, '_vpp_build', 'drafts')


def han(s):
    return sum(1 for c in s if '\u4e00' <= c <= '\u9fff')


def classify(lines):
    cls, in_code, in_fig = [], False, False
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
            cls.append('c')
            continue
        if st.startswith(':::figure'):
            in_fig = True
            cls.append('f')
            continue
        cls.append('t' if st.startswith('|') else ('h' if st.startswith('#') else ('b' if not st else 'n')))
    return cls


def main():
    vol = sys.argv[1]
    p = os.path.join(DRAFTS, vol + '.txt')
    lines = open(p, encoding='utf-8').read().split('\n')
    cls = classify(lines)

    # 篇切分
    arts, cur = [], None
    for i, (l, c) in enumerate(zip(lines, cls)):
        m = re.match(r'^## (\d\d-\d\d)\s+(.*\S)\s*$', l) if c == 'h' else None
        if m:
            if cur:
                arts.append(cur)
            cur = {'id': m.group(1), 'title': m.group(2), 'start': i, 'end': len(lines)}
        elif cur:
            cur['end'] = i + 1
    if cur:
        arts.append(cur)

    print(f'=== {vol}.txt  {len(arts)} 篇  总行数 {len(lines)} ===')
    for a in arts:
        seg = '\n'.join(lines[a['start']:a['end']])
        h = han(seg)
        mark = '  << 需扩写' if h < 3200 else ''
        print(f"  {a['id']}  全文汉字={h:5d}  行 {a['start']+1}-{a['end']}{mark}  {a['title'][:34]}")

    print('\n--- 图块缺引导句 / 缺图号引用 ---')
    for i, (l, c) in enumerate(zip(lines, cls)):
        if c == 'f' and l.strip().startswith(':::figure'):
            fid = (re.search(r'id=(\S+)', l) or [None, '?'])[1]
            j = i - 1
            while j >= 0 and cls[j] == 'b':
                j -= 1
            ok = cls[j] == 'n' if j >= 0 else False
            cited = False
            if ok:
                cited = fid in lines[j]
            flag = 'OK ' if (ok and cited) else ('缺句' if not ok else '缺引用')
            print(f'  L{i+1:5d} {fid} [{flag}] 前文: {lines[j][:56] if j >= 0 else ""}')

    print('\n--- 表格缺引导句 ---')
    for i, (l, c) in enumerate(zip(lines, cls)):
        if c == 't' and '|' in l and i + 1 < len(lines) and re.match(r'^\|[\s:\-|]+\|$', lines[i + 1].strip()):
            j = i - 1
            while j >= 0 and cls[j] == 'b':
                j -= 1
            if j >= 0 and cls[j] != 'n':
                print(f'  L{i+1:5d} 前接 {cls[j]}: {lines[j][:56]}')
                print(f'         表头: {l[:70]}')

    print('\n--- 超限图（节点>10 或 边>12）---')
    for i, (l, c) in enumerate(zip(lines, cls)):
        if c == 'f' and l.strip().startswith(':::figure'):
            j = i + 1
            nodes = 0
            edges = 0
            while j < len(lines) and lines[j].strip() != ':::':
                if lines[j].startswith('node '):
                    nodes += 1
                elif lines[j].startswith('edge '):
                    edges += 1
                j += 1
            if nodes > 10 or edges > 12:
                fid = (re.search(r'id=(\S+)', l) or [None, '?'])[1]
                print(f'  L{i+1:5d} {fid} 节点={nodes} 边={edges}')


if __name__ == '__main__':
    main()
