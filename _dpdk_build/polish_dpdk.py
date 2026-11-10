# -*- coding: utf-8 -*-
"""确定性收尾修复：为缺少前置引导句的图块补一句中文引导。"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')

LEADS = {
    '03-01-02': '同 Socket 绑定的资源关系如图 03-01-02 所示：网卡、lcore 与大页内存应尽量落在同一 NUMA 节点。',
    '03-05-02': '四种虚拟化数据通路的路径与性能特征对比见图 03-05-02。',
    '03-06-02': '多实例场景下 file-prefix 与共享资源的隔离关系如图 03-06-02 所示。',
    '04-08-02': '配置未生效时的分层排查决策链见图 04-08-02。',
    '08-06-01': '生产运维闭环与上线门禁流程如图 08-06-01 所示。',
}

changed = 0
for code in sorted({fid[:2] for fid in LEADS}):
    p = os.path.join(DRAFTS, code + '.txt')
    lines = open(p, encoding='utf-8').read().splitlines()
    out = []
    for line in lines:
        if line.strip().startswith(':::figure'):
            fid = None
            for k in LEADS:
                if 'id=' + k in line:
                    fid = k
                    break
            if fid:
                ctx = ' '.join(out[-4:])
                if not any(w in ctx for w in ('图', '如下', '下图', '示意', '流程', '关系', '架构', '链路', '布局', '拓扑')):
                    out.append(LEADS[fid])
                    out.append('')
                    changed += 1
        out.append(line)
    open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

print('补充图前引导句:', changed, '处')
