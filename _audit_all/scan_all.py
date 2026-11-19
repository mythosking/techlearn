# -*- coding: utf-8 -*-
"""跨 8 套资料统一扫描：逐篇统计严格汉字/图/表/码块，定位薄篇与缺口。只读，不改文件。"""
import os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作区根
PROJECTS = [
    ('_hs_build', 'Hyperscan'), ('_suricata_build', 'Suricata'),
    ('_snort_build', 'Snort3'), ('_sonic_build', 'SONiC'),
    ('_vpp_build', 'VPP'), ('_dpdk_build', 'DPDK'),
    ('_openvpn_build', 'OpenVPN'), ('_wgwin_build', 'WireGuard-Win'),
]

def strict_cjk(text):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith(':::figure'):
            while i < len(lines) and not lines[i].strip().startswith(':::'):
                i += 1
            i += 1; continue
        if s.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1; continue
        if s.startswith('|'):
            i += 1; continue
        out.append(lines[i]); i += 1
    return len(re.findall(r'[\u4e00-\u9fff]', '\n'.join(out)))

def count_blocks(text):
    figs = len(re.findall(r'^:::figure', text, re.M))
    # 表格：表头行紧跟分隔行
    lines = text.splitlines(); tabs = 0
    for i in range(len(lines)-1):
        if lines[i].strip().startswith('|') and re.match(r'^\s*\|?[\s:\-\|]+\|[\s:\-\|]*$', lines[i+1]) and '-' in lines[i+1]:
            tabs += 1
    codes = len(re.findall(r'^```\w', text, re.M))
    return figs, tabs, codes

def main():
    rows = []
    for bdir, label in PROJECTS:
        drafts = os.path.join(BASE, bdir, 'drafts')
        for code in ['01','02','03','04','05','06','07','08']:
            p = os.path.join(drafts, code + '.txt')
            if not os.path.exists(p):
                continue
            src = open(p, encoding='utf-8').read()
            marks = [(m.start(), m.group(1)) for m in re.finditer(r'^##\s+(\d{2}-\d{2})\s+', src, re.M)]
            for k,(pos,sid) in enumerate(marks):
                end = marks[k+1][0] if k+1 < len(marks) else len(src)
                body = src[pos:end]
                cjk = strict_cjk(body)
                f,t,c = count_blocks(body)
                rows.append((label, sid, cjk, f, t, c))

    print('=== 总篇数 ===', len(rows))
    thin = [r for r in rows if r[2] < 3200]
    print('\n=== 薄篇（严格汉字 < 3200）共 %d 篇 ===' % len(thin))
    for label,sid,cjk,f,t,c in sorted(thin, key=lambda x:x[2]):
        print('  %-14s %s 字=%4d 图=%d 表=%d 码=%d' % (label,sid,cjk,f,t,c))

    for idx,name in [(3,'无图'),(4,'无表'),(5,'无带语言码块')]:
        miss = [r for r in rows if r[idx]==0]
        print('\n=== %s篇 共 %d 篇 ===' % (name,len(miss)))
        for label,sid,cjk,f,t,c in miss:
            print('  %-14s %s 字=%4d 图=%d 表=%d 码=%d' % (label,sid,cjk,f,t,c))

    print('\n=== 各项目最低字数 TOP3 ===')
    for label,_ in PROJECTS:
        pr = sorted([r for r in rows if r[0]==label], key=lambda x:x[2])[:3]
        if pr:
            print('  %-14s ' % label + ' | '.join('%s:%d'%(r[1],r[2]) for r in pr))

if __name__ == '__main__':
    main()
