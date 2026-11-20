# -*- coding: utf-8 -*-
"""把 drafts/NNx.txt 分片合并成交付用的 drafts/NN.txt（标题标准化、去哨兵、压空行）。"""
import os, re, json, glob

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')
CFG = json.load(open(os.path.join(BASE, 'project.json'), encoding='utf-8'))
NAME = CFG['name']

BOOKS = {
    '01': '基础与概述', '02': '编译与构建', '03': '集成与部署',
    '04': '参数与 API 手册', '05': '关键数据结构字段详解',
    '06': '技术原理', '07': '模块与特性介绍', '08': '运维、性能基准与排障',
}
EXPECT = {'01': 4, '02': 5, '03': 6, '04': 8,
          '05': 9, '06': 14, '07': 13, '08': 6}


def main():
    for code, book in BOOKS.items():
        parts = sorted(glob.glob(os.path.join(DRAFTS, code + '[a-z].txt')))
        final = os.path.join(DRAFTS, code + '.txt')
        if not parts:
            print('[SKIP] %s 无分片（%s）' % (code, '已就绪' if os.path.exists(final) else '仍缺失'))
            continue
        bodies = []
        for p in parts:
            s = open(p, encoding='utf-8').read().replace('<!--NEXT-->', '').replace('\r\n', '\n')
            first = next((i for i, l in enumerate(s.split('\n')) if l.startswith('## ' + code + '-')), None)
            if first is None:
                print('[WARN] %s 无正文二级标题' % os.path.basename(p)); continue
            bodies.append('\n'.join(s.split('\n')[first:]).strip('\n'))
        title = '# %s 技术资料 · %s %s' % (NAME, code, book)
        text = title + '\n\n' + '\n\n'.join(bodies) + '\n'
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        open(final, 'w', encoding='utf-8').write(text)
        ids = re.findall(r'^## (%s-\d{2})\s' % code, text, re.M)
        want = ['%s-%02d' % (code, i) for i in range(1, EXPECT[code] + 1)]
        print('[OK] %s.txt: %d 篇 %s~%s, 图 %d, 编号 %s, 哨兵 %d'
              % (code, len(ids), ids[0] if ids else '-', ids[-1] if ids else '-',
                 len(re.findall(r'^:::figure', text, re.M)),
                 'OK' if ids == want else 'CHECK ' + ','.join(ids), text.count('NEXT')))


if __name__ == '__main__':
    main()
