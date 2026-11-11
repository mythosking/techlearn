# -*- coding: utf-8 -*-
"""
把结构化 Markdown 内容源编译为 DOCX：
- 标题 / 段落 / 列表 / 引用 / 表格 / 代码块 -> Word 原生对象
- ```mermaid 与 :::figure 图块 -> Word 原生可编辑形状组 + .drawio 源文件
用法: python md2docx.py <input.md> <output.docx> <figures_dir> [title] [subtitle]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from vpp_docgen import build_docx
from vpp_figdsl import parse_dsl, parse_mermaid

FIG_SEQ = [0]


def _clean_inline(s):
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    return s.replace('\\|', '|').strip()


def _split_table_row(line):
    # 表格里被转义的 \|（shell 管道、命令语法中的「或」）不是列分隔符
    s = line.strip()
    s = re.sub(r'^\|', '', s)
    s = re.sub(r'(?<!\\)\|$', '', s)
    return [c.strip() for c in re.split(r'(?<!\\)\|', s)]


def _is_table_sep(line):
    return bool(re.match(r'^\s*\|?[\s:\-\|]+\|[\s:\-\|]*$', line)) and '-' in line


def parse_md(src, doc_code='00'):
    lines = src.splitlines()
    blocks = []
    title = None
    subtitle = None
    meta = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 图 DSL 块
        if stripped.startswith(':::figure'):
            buf = [stripped]
            i += 1
            while i < n and not lines[i].strip().startswith(':::'):
                buf.append(lines[i])
                i += 1
            i += 1
            FIG_SEQ[0] += 1
            fig = parse_dsl('\n'.join(buf), f'{doc_code}-FIG-{FIG_SEQ[0]:02d}')
            # 图题使用内容源里的图 id，与正文引用、.drawio 文件名三者一致
            blocks.append({'t': 'figure', 'fig': fig,
                           'caption': f"图 {fig['id']}  {fig['name']}（可编辑 · 附 draw.io 源文件）"})
            continue

        # 代码块（含 mermaid）
        if stripped.startswith('```'):
            lang = stripped[3:].strip().lower()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            body = '\n'.join(buf)
            if lang == 'mermaid':
                FIG_SEQ[0] += 1
                fig = parse_mermaid(body, f'{doc_code}-FIG-{FIG_SEQ[0]:02d}', '流程图')
                if fig['nodes']:
                    blocks.append({'t': 'figure', 'fig': fig,
                                   'caption': f"图 {fig['id']}  {fig['name']}（可编辑 · 附 draw.io 源文件）"})
                    continue
            blocks.append({'t': 'code', 'text': body, 'lang': lang or 'text'})
            continue

        # 标题
        m = re.match(r'^(#{1,4})\s+(.*)', stripped)
        if m:
            lv, txt = len(m.group(1)), _clean_inline(m.group(2))
            if lv == 1 and title is None:
                title = txt
            elif lv == 2:
                blocks.append({'t': 'h1', 'text': txt})
            elif lv == 3:
                blocks.append({'t': 'h2', 'text': txt})
            else:
                blocks.append({'t': 'h3', 'text': txt})
            i += 1
            continue

        # 表格
        if stripped.startswith('|') and i + 1 < n and _is_table_sep(lines[i + 1]):
            header = [_clean_inline(c) for c in _split_table_row(stripped)]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append([_clean_inline(c) for c in _split_table_row(lines[i])])
                i += 1
            blocks.append({'t': 'table', 'header': header, 'rows': rows})
            continue

        # 引用 / 提示
        if stripped.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(_clean_inline(lines[i].strip().lstrip('>').strip()))
                i += 1
            blocks.append({'t': 'note', 'text': '  '.join(buf)})
            continue

        # 列表
        if re.match(r'^[-*+]\s+', stripped):
            items = []
            while i < n and re.match(r'^[-*+]\s+', lines[i].strip()):
                items.append(_clean_inline(re.sub(r'^[-*+]\s+', '', lines[i].strip())))
                i += 1
            blocks.append({'t': 'bullets', 'items': items})
            continue
        if re.match(r'^\d+[.)]\s+', stripped):
            items = []
            while i < n and re.match(r'^\d+[.)]\s+', lines[i].strip()):
                items.append(_clean_inline(re.sub(r'^\d+[.)]\s+', '', lines[i].strip())))
                i += 1
            blocks.append({'t': 'nums', 'items': items})
            continue

        # 分隔线
        if stripped in ('---', '***', '___'):
            i += 1
            continue

        # 元信息行（粗体键值）
        if stripped.startswith('>') is False and re.match(r'^\*\*[^*]+\*\*', stripped) and title and not blocks:
            meta.append(_clean_inline(stripped))
            i += 1
            continue

        # 普通段落
        if stripped:
            buf = [stripped]
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if (not nxt or nxt.startswith(('#', '>', '|', '```', ':::'))
                        or re.match(r'^[-*+]\s+', nxt) or re.match(r'^\d+[.)]\s+', nxt)
                        or nxt in ('---', '***', '___')):
                    break
                buf.append(nxt)
                i += 1
            txt = _clean_inline(' '.join(buf))
            if txt:
                blocks.append({'t': 'p', 'text': txt})
            continue
        i += 1

    return {'title': title or 'VPP 技术资料', 'subtitle': subtitle,
            'meta': meta[:4], 'blocks': blocks}


def convert(md_path, docx_path, figures_dir, title=None, subtitle=None, doc_code='00'):
    with open(md_path, 'r', encoding='utf-8') as f:
        src = f.read()
    FIG_SEQ[0] = 0
    spec = parse_md(src, doc_code)
    if title:
        spec['title'] = title
    if subtitle:
        spec['subtitle'] = subtitle
    return build_docx(spec, docx_path, figures_dir)


if __name__ == '__main__':
    md, out, figs = sys.argv[1], sys.argv[2], sys.argv[3]
    t = sys.argv[4] if len(sys.argv) > 4 else None
    s = sys.argv[5] if len(sys.argv) > 5 else None
    code = sys.argv[6] if len(sys.argv) > 6 else '00'
    r = convert(md, out, figs, t, s, code)
    print('DOCX:', r['docx'])
    print('figures:', r['figure_count'])
    print('blocks:', len(parse_md(open(md, encoding='utf-8').read(), code)['blocks']))
    for m in r['figures']:
        print('  -', m['id'], '->', os.path.basename(m['drawio']))
