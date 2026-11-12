# -*- coding: utf-8 -*-
"""把分片草稿合并为单册：04.txt = 04 + 04b + 04c ；06.txt = 06a + 06b"""
import os, re

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drafts')


def merge(out_name, parts):
    chunks = []
    title = None
    for p in parts:
        fp = os.path.join(D, p)
        if not os.path.exists(fp):
            print('[MISS]', p)
            continue
        s = open(fp, encoding='utf-8').read()
        s = s.replace('<!--NEXT-->', '').replace('\r\n', '\n')
        lines = s.split('\n')
        idx = 0
        for i, ln in enumerate(lines):
            if ln.startswith('# '):
                if title is None:
                    title = ln.strip()
                idx = i + 1
                break
        body = '\n'.join(lines[idx:]).strip('\n')
        chunks.append(body)
    txt = title + '\n\n' + '\n\n'.join(chunks) + '\n'
    txt = re.sub(r'\n{4,}', '\n\n\n', txt)
    open(os.path.join(D, out_name), 'w', encoding='utf-8').write(txt)
    arts = re.findall(r'^## (\d\d-\d\d)\s', txt, re.M)
    print(f'[OK] {out_name}: {len(txt)} 字符, {len(arts)} 篇 -> {arts}, 图 {len(re.findall(r"^:::figure", txt, re.M))}')


merge('04.txt', ['04.txt', '04b.txt', '04c.txt'])
merge('06.txt', ['06a.txt', '06b.txt'])
