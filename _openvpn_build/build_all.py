# -*- coding: utf-8 -*-
"""把 drafts/00..08.txt 批量编译为交付目录里的 9 个 DOCX（含可编辑图形 + .drawio 源）"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2docx import convert

BASE = r'C:\Users\mythos\SynologyDrive\技术学习'
BUILD = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BUILD, 'drafts')
OUT = os.path.join(BASE, 'OpenVPN技术资料')
FIGS = os.path.join(OUT, 'figures')

DOCS = [
    ('00', '00_总目录与阅读指南.docx', 'OpenVPN 技术资料 · 总目录与阅读指南（交付版）',
     '9 个 DOCX · 62 篇 · 配图 / 表格 / 示例约定'),
    ('01', '01_基础与概述.docx', 'OpenVPN 技术资料 · 01 基础与概述', '4 篇 · 01-01 ~ 01-04'),
    ('02', '02_编译与构建.docx', 'OpenVPN 技术资料 · 02 编译与构建', '5 篇 · 02-01 ~ 02-05'),
    ('03', '03_部署与环境配置.docx', 'OpenVPN 技术资料 · 03 部署与环境配置', '6 篇 · 03-01 ~ 03-06'),
    ('04', '04_配置与命令行.docx', 'OpenVPN 技术资料 · 04 配置与命令行',
     '8 篇 · 04-01 ~ 04-08（配置与命令唯一权威源）'),
    ('05', '05_关键数据结构字段详解.docx', 'OpenVPN 技术资料 · 05 关键数据结构字段详解',
     '9 篇 · 05-01 ~ 05-09（结构体字段唯一权威源 / 工具书随查）'),
    ('06', '06_技术原理.docx', 'OpenVPN 技术资料 · 06 技术原理',
     '12 篇 · 06-01 ~ 06-12（机制与调用链唯一权威源）'),
    ('07', '07_模块与特性介绍.docx', 'OpenVPN 技术资料 · 07 模块与特性介绍',
     '12 篇 · 07-01 ~ 07-12（模块功能唯一权威源）'),
    ('08', '08_运维、性能基准与排障.docx', 'OpenVPN 技术资料 · 08 运维、性能基准与排障',
     '6 篇 · 08-01 ~ 08-06'),
]

SUBTITLE = ('版本基准 OpenVPN 2.6.x / 2.7(master) / ovpn-dco ｜ 深度技术型 ｜ '
            '配图为 Word 原生可编辑形状 + draw.io 源文件')


def main():
    os.makedirs(FIGS, exist_ok=True)
    report = []
    for code, fname, title, subtitle in DOCS:
        src = os.path.join(DRAFTS, code + '.txt')
        if not os.path.exists(src):
            print(f'[SKIP] {code}: 缺内容源 {src}')
            report.append({'code': code, 'status': 'missing'})
            continue
        r = convert(src, os.path.join(OUT, fname), FIGS, title, subtitle, code)
        size = os.path.getsize(r['docx'])
        print(f"[OK] {fname}: {r['figure_count']} 图, {size} bytes")
        report.append({'code': code, 'docx': fname, 'figures': r['figure_count'],
                       'bytes': size,
                       'drawio': [os.path.basename(m['drawio']) for m in r['figures']],
                       'status': 'ok'})
    with open(os.path.join(BUILD, 'build_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    ok = sum(1 for x in report if x['status'] == 'ok')
    print(f'\n合计: {ok}/{len(DOCS)} 个文档, '
          f'{sum(x.get("figures", 0) for x in report)} 张可编辑图')


if __name__ == '__main__':
    main()
