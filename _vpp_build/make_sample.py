# -*- coding: utf-8 -*-
"""生成一份验收样例：验证 DOCX 内图形是 Word 原生可编辑形状，并同步产出 .drawio 源文件"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from vpp_docgen import build_docx, edge_between

OUT_DIR = r'C:\Users\mythos\SynologyDrive\技术学习\VPP技术资料'
FIG_DIR = os.path.join(OUT_DIR, 'figures')

fig = {
    'id': 'SAMPLE-01',
    'name': 'VPP 分层架构与数据面控制面分离',
    'width': 600,
    'height': 372,
    'nodes': [
        {'id': 'ctl1', 'x': 40,  'y': 16,  'w': 150, 'h': 42, 'text': 'vppctl / CLI', 'tone': 'purple'},
        {'id': 'ctl2', 'x': 225, 'y': 16,  'w': 150, 'h': 42, 'text': 'Honeycomb / NETCONF', 'tone': 'purple', 'fs': 9},
        {'id': 'ctl3', 'x': 410, 'y': 16,  'w': 150, 'h': 42, 'text': 'govpp / Python API', 'tone': 'purple', 'fs': 9},
        {'id': 'api',  'x': 150, 'y': 92,  'w': 300, 'h': 44, 'text': 'Binary API / 共享内存消息队列', 'tone': 'blue', 'fs': 10},
        {'id': 'vnet', 'x': 150, 'y': 168, 'w': 300, 'h': 44, 'text': 'vnet + plugins（转发功能图）', 'tone': 'teal', 'fs': 10},
        {'id': 'vlib', 'x': 40,  'y': 244, 'w': 230, 'h': 44, 'text': 'vlib（图节点 / 帧调度）', 'tone': 'teal', 'fs': 10},
        {'id': 'infra', 'x': 330, 'y': 244, 'w': 230, 'h': 44, 'text': 'vppinfra（vec / pool / hash）', 'tone': 'teal', 'fs': 10},
        {'id': 'pmd',  'x': 150, 'y': 318, 'w': 300, 'h': 42, 'text': 'DPDK PMD / NIC（轮询收发）', 'tone': 'amber', 'fs': 10},
    ],
    'edges': [
        {'x1': 115, 'y1': 58, 'x2': 260, 'y2': 92, 'arrow': True},
        {'x1': 300, 'y1': 58, 'x2': 300, 'y2': 92, 'arrow': True},
        {'x1': 485, 'y1': 58, 'x2': 340, 'y2': 92, 'arrow': True},
        {'x1': 300, 'y1': 136, 'x2': 300, 'y2': 168, 'arrow': True, 'text': '控制面下发', 'label_w': 84},
        {'x1': 300, 'y1': 212, 'x2': 155, 'y2': 244, 'arrow': True},
        {'x1': 300, 'y1': 212, 'x2': 445, 'y2': 244, 'arrow': True},
        {'x1': 155, 'y1': 288, 'x2': 260, 'y2': 318, 'arrow': True},
        {'x1': 445, 'y1': 288, 'x2': 340, 'y2': 318, 'arrow': True},
        {'x1': 40, 'y1': 37, 'x2': 40, 'y2': 339, 'arrow': False, 'dashed': True, 'line': 'B4B2A9'},
    ],
}

spec = {
    'title': 'VPP 技术资料 · 图形验收样例',
    'subtitle': 'Word 原生形状（可编辑） + draw.io 源文件',
    'meta': ['版本基准 VPP 23.06 / master', '2026-11-10', '样例 SAMPLE'],
    'blocks': [
        {'t': 'note', 'text': '验收要点：在 Word 中单击下图任意一个方框，应能单独选中并直接修改文字、'
                              '拖动位置、更改填充色；箭头也可单独选中。整张图不是一张图片。'},
        {'t': 'h1', 'text': '1. 架构示意'},
        {'t': 'p', 'text': 'VPP 采用数据面与控制面分离的分层结构。控制面通过 Binary API 经共享内存消息队列与'
                           '数据面交互，数据面内部则由 vnet 功能图、vlib 图节点调度器与 vppinfra 基础容器构成，'
                           '底层由 DPDK PMD 以轮询方式从网卡批量收取报文。'},
        {'t': 'figure', 'fig': fig, 'caption': '图 SAMPLE-1  VPP 分层架构与数据面控制面分离（可编辑）'},
        {'t': 'h2', 'text': '1.1 关键结构对照'},
        {'t': 'table',
         'header': ['层次', '核心职责', '典型源码位置'],
         'rows': [
             ['控制面', '配置下发、状态订阅', 'src/vpp-api/、src/vlibapi/'],
             ['Binary API', '消息序列化与跨进程通信', 'src/vlibapi/api_helper.c'],
             ['vnet / plugins', '转发功能图与特性弧', 'src/vnet/、src/plugins/'],
             ['vlib', '图节点注册、帧调度、缓冲区', 'src/vlib/node.c、src/vlib/main.c'],
             ['vppinfra', '向量、池、散列、位图', 'src/vppinfra/vec.h、pool.h'],
         ],
         'widths': [3.2, 6.0, 6.0]},
        {'t': 'h2', 'text': '1.2 命令示例'},
        {'t': 'code', 'text': 'vppctl show interface\nvppctl show runtime\nvppctl show errors'},
        {'t': 'p', 'text': '上述表格与代码块同样是 Word 原生表格与段落，可直接编辑，不含任何位图截图。'},
        {'t': 'h1', 'text': '2. 图形源文件'},
        {'t': 'p', 'text': '与本图对应的 .drawio 源文件已输出到 figures/ 目录，可用 draw.io（diagrams.net）'
                           '或 VS Code 的 Draw.io Integration 插件打开，继续拖拽调整节点与连线。'},
    ],
}

res = build_docx(spec, os.path.join(OUT_DIR, '_样例_可编辑图形验收.docx'), FIG_DIR)
print('DOCX:', res['docx'])
print('figure_count:', res['figure_count'])
for m in res['figures']:
    print('  -', m['id'], '->', m['drawio'])
