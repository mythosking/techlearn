# -*- coding: utf-8 -*-
"""生成待扩写清单：用与 Snort/SONiC audit_content.py 完全一致的 strict_cjk 口径。
输出 JSON + 控制台，供分批派发。只读。"""
import os, re, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = [
    ('_hs_build','Hyperscan'),('_suricata_build','Suricata'),('_snort_build','Snort3'),
    ('_sonic_build','SONiC'),('_vpp_build','VPP'),('_dpdk_build','DPDK'),
    ('_openvpn_build','OpenVPN'),('_wgwin_build','WireGuard-Win'),
]
TARGET = {'VPP','WireGuard-Win','DPDK'}  # 需提升的老项目
THRESHOLD = 3200

def strict_cjk(text):
    out, skip, lines, i = [], False, text.splitlines(), 0
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

def main():
    gaps = []
    for bdir, label in PROJECTS:
        if label not in TARGET: continue
        drafts = os.path.join(BASE, bdir, 'drafts')
        for code in ['01','02','03','04','05','06','07','08']:
            p = os.path.join(drafts, code+'.txt')
            if not os.path.exists(p): continue
            src = open(p, encoding='utf-8').read()
            marks = [(m.start(), m.group(1), m.group(2).strip()) for m in re.finditer(r'^##\s+(\d{2}-\d{2})\s+(.+)$', src, re.M)]
            for k,(pos,sid,title) in enumerate(marks):
                end = marks[k+1][0] if k+1 < len(marks) else len(src)
                body = src[pos:end]
                cjk = strict_cjk(body)
                if cjk < THRESHOLD:
                    gaps.append({'project':label,'bdir':bdir,'doc':code,'id':sid,'title':title,
                                 'cjk':cjk,'need':THRESHOLD-cjk,'file':code+'.txt'})
    gaps.sort(key=lambda x:(x['project'], x['id']))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gap_list.json')
    json.dump(gaps, open(out,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    cnt = Counter(g['project'] for g in gaps)
    print('=== 待扩写篇数（纯叙述汉字<3200）===', dict(cnt), '合计', len(gaps))
    print('=== 缺口总字数 ===', sum(g['need'] for g in gaps))
    for g in gaps:
        print('  %-14s %s 字=%4d 缺=%4d  %s' % (g['project'],g['id'],g['cjk'],g['need'],g['title'][:34]))
    print('清单已写入', out)

if __name__ == '__main__':
    main()
