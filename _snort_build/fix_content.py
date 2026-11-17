# -*- coding: utf-8 -*-
"""内容源确定性修复：代码块语言标注 + 图节点长文字自动折行。
用法: python fix_content.py [--apply]   默认 dry-run 只报告。
"""
import os
import re
import sys
import glob
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(BASE, 'drafts')
APPLY = '--apply' in sys.argv
MAXW = 38


def disp(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def guess_lang(body):
    b = body
    if re.search(r'\b(vppctl|systemctl|dpdk-devbind|driverctl|modprobe|lspci|ethtool|'
                 r'qemu-system|docker|kubectl|apt-get|dpkg |make |cmake |ninja|'
                 r'mount |grep |sudo |export |sysctl|hugeadm|taskset|numactl|'
                 r'tcpdump|iperf|trex|gdb|perf |curl |ss -|ip link|ip addr|'
                 r'echo |cat /|tail |head |awk |sed |chmod |chown |ln -s|'
                 r'bash |sh |/bin/|./|virsh |ethtool|lshw|dmesg|free -|top -)', b, re.I):
        return 'bash'
    if re.search(r'^\s*(#include|typedef|struct\s|static\s|void\s*$|u32 |u64 |uword |'
                 r'int\s|clib_|vlib_|vnet_|VLIB_|VNET_|format_|always_inline)', b, re.M) \
            or re.search(r'\b(vec_add1|vec_validate|pool_get|pool_put|vec_free|'
                         r'clib_bihash|dlopen|dlsym)\s*\(', b):
        return 'c'
    if re.search(r'^\s*(unix|dpdk|cpu|buffers|plugins|statseg|socksvr|api-segment|'
                 r'cli-listen|logging|heapsize|main-core|corelist-workers)\s*[\{\s]', b, re.M):
        return 'ini'
    if re.search(r'^\s*(apiVersion|kind|metadata|spec):', b, re.M):
        return 'yaml'
    if re.search(r'^\s*(import |from \S+ import|def |print\()', b, re.M):
        return 'python'
    if re.search(r'^\s*(FROM |RUN |COPY |ENTRYPOINT |CMD )', b, re.M):
        return 'dockerfile'
    if re.search(r'^\s*(interface|router|route|neighbor|bridge-domain)\s', b, re.M):
        return 'text'
    return 'text'


def wrap_line(s, maxw=MAXW):
    if disp(s) <= maxw:
        return [s]
    best = None
    for sep in [' / ', '、', ' · ', '，', ', ', ' /', '／', ' ', '/', ',']:
        for m in re.finditer(re.escape(sep), s):
            pos = m.start() + len(sep)
            left, right = s[:pos].rstrip(' /、·，,'), s[pos:].lstrip(' /、·，,')
            if not left or not right:
                continue
            if disp(left) <= maxw and disp(right) <= maxw:
                score = abs(disp(left) - disp(right))
                if best is None or score < best[0]:
                    best = (score, left, right)
    if best:
        return [best[1], best[2]]
    # 无合适分隔符：按显示宽度就近硬切（尽量不切断 ASCII 单词）
    acc, cut = 0, len(s)
    for i, ch in enumerate(s):
        acc += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if acc >= maxw:
            cut = i + 1
            break
    return [s[:cut].rstrip(), s[cut:].lstrip()]


def fix_node_line(line):
    m = re.match(r'^(\s*node\s+\S+\s+")([^"]*)("\s*(?:\w+)?\s*)$', line)
    if not m:
        return line, False
    text = m.group(2)
    parts = re.split(r'<br\s*/?>', text, flags=re.I)
    out = []
    for p in parts:
        out.extend(wrap_line(p))
    # 最多三行，避免节点过高
    if len(out) > 3:
        out = out[:2] + [' / '.join(out[2:])]
    new_text = '<br/>'.join(x for x in out if x)
    if new_text == text:
        return line, False
    return m.group(1) + new_text + m.group(3), True


def main():
    total_lang = total_wrap = 0
    lang_count = {}
    details = []
    for p in sorted(glob.glob(os.path.join(DRAFTS, '0[1-8].txt'))):
        src = open(p, encoding='utf-8').read()
        lines = src.splitlines()
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith('```'):
                # 只处理代码块的开始行；结束行以 ``` 开头也必须一并跳过
                has_lang = bool(s[3:].strip())
                j = i + 1
                body = []
                while j < len(lines) and not lines[j].strip().startswith('```'):
                    body.append(lines[j])
                    j += 1
                if not has_lang:
                    lang = guess_lang('\n'.join(body))
                    lines[i] = '```' + lang
                    lang_count[lang] = lang_count.get(lang, 0) + 1
                    total_lang += 1
                i = j + 1
                continue
            if s.startswith('node ') and '"' in s:
                nl, changed = fix_node_line(lines[i])
                if changed:
                    total_wrap += 1
                    details.append((os.path.basename(p), i + 1, s[:60], nl.strip()[:100]))
                lines[i] = nl
            i += 1
        out = '\n'.join(lines) + '\n'
        if src != out:
            if APPLY:
                open(p, 'w', encoding='utf-8').write(out)
            print('%s: %s (%d 行)' % (os.path.basename(p), '已写入' if APPLY else 'dry-run', len(lines)))
    print('\n语言标注补齐: %d 个 %s' % (total_lang, lang_count))
    print('节点文字折行: %d 行' % total_wrap)
    print('\n=== 折行明细（前 30）===')
    for d in details[:30]:
        print('  %s L%-5d\n    旧: %s\n    新: %s' % d)


if __name__ == '__main__':
    main()
