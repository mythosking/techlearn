# -*- coding: utf-8 -*-
"""
VPP 技术资料 DOCX 生成器
- 正文：标题/段落/表格/代码块/提示框
- 配图：编译成 Word 原生形状组（DrawingML wps/wpg，可在 Word/WPS 里逐个选中、改字、拖动、改色）
        并提供 VML Fallback 兼容旧版
- 同时为每张图输出一份 .drawio 源文件（mxGraphModel，可用 draw.io / VS Code Draw.io 插件打开继续编辑）
"""
import os
import html
from datetime import datetime

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.oxml import parse_xml

EMU = 9525  # 1 px = 9525 EMU

NSDECL = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word"'
)

PALETTE = {
    'blue':   ('#E6F1FB', '#185FA5'),
    'teal':   ('#E1F5EE', '#0F6E56'),
    'amber':  ('#FAEEDA', '#854F0B'),
    'purple': ('#EEEDFE', '#534AB7'),
    'gray':   ('#F1EFE8', '#5F5E5A'),
    'red':    ('#FCEBEB', '#A32D2D'),
    'green':  ('#EAF3DE', '#3B6D11'),
}


def esc(s):
    return html.escape(str(s), quote=True)


def px(v):
    return int(round(float(v) * EMU))


def _node_colors(n):
    tone = n.get('tone', 'blue')
    fill, line = PALETTE.get(tone, PALETTE['blue'])
    return n.get('fill', fill.lstrip('#')), n.get('line', line.lstrip('#'))


# ---------------------------------------------------------------- DrawingML
def _txbx_content(text, font_halfpt=20, align='center', color='2C2C2A', bold=False):
    b = '<w:b/>' if bold else ''
    lines = str(text).split('\n')
    ps = []
    for ln in lines:
        ps.append(
            '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:jc w:val="{align}"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="微软雅黑"/>'
            f'{b}<w:sz w:val="{font_halfpt}"/><w:szCs w:val="{font_halfpt}"/>'
            f'<w:color w:val="{color}"/></w:rPr>'
            f'<w:t xml:space="preserve">{esc(ln)}</w:t></w:r></w:p>'
        )
    return ''.join(ps)


def _wsp_node(n):
    x, y, w, h = px(n['x']), px(n['y']), px(n['w']), px(n['h'])
    fill, line = _node_colors(n)
    shape = n.get('shape', 'roundRect')
    fs = int(float(n.get('fs', 10)) * 2)
    body = _txbx_content(n.get('text', ''), fs, n.get('align', 'center'))
    lw = n.get('lw', 9525)
    return f'''<wps:wsp>
<wps:cNvSpPr txBox="1"/>
<wps:spPr>
<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
<a:prstGeom prst="{shape}"><a:avLst/></a:prstGeom>
<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>
<a:ln w="{lw}" cap="flat"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill><a:prstDash val="solid"/></a:ln>
</wps:spPr>
<wps:txbx><w:txbxContent>{body}</w:txbxContent></wps:txbx>
<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="45720" tIns="27432" rIns="45720" bIns="27432"
 anchor="ctr" anchorCtr="0" forceAA="0" compatLnSpc="1">
<a:prstTxWarp prst="textNoShape"><a:avLst/></a:prstTxWarp><a:noAutofit/>
</wps:bodyPr>
</wps:wsp>'''


def _wsp_edge(e):
    x1, y1, x2, y2 = px(e['x1']), px(e['y1']), px(e['x2']), px(e['y2'])
    dx, dy = x2 - x1, y2 - y1
    left, top = min(x1, x2), min(y1, y2)
    cx, cy = max(1, abs(dx)), max(1, abs(dy))
    flip_h = '1' if dx < 0 else '0'
    flip_v = '1' if dy < 0 else '0'
    color = e.get('line', '5F5E5A').lstrip('#')
    dashed = '<a:prstDash val="dash"/>' if e.get('dashed') else '<a:prstDash val="solid"/>'
    arrow = '<a:tailEnd type="triangle" w="sm" len="sm"/>' if e.get('arrow', True) else ''
    return f'''<wps:wsp>
<wps:cNvSpPr/>
<wps:spPr>
<a:xfrm flipH="{flip_h}" flipV="{flip_v}"><a:off x="{left}" y="{top}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:prstGeom prst="line"><a:avLst/></a:prstGeom>
<a:noFill/>
<a:ln w="12700" cap="flat"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{dashed}{arrow}</a:ln>
</wps:spPr>
<wps:bodyPr/>
</wps:wsp>'''


def _wsp_edge_label(e):
    """连线标签：无边框无填充的文本框"""
    if not e.get('text'):
        return ''
    x1, y1, x2, y2 = float(e['x1']), float(e['y1']), float(e['x2']), float(e['y2'])
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    tw = float(e.get('label_w', 88))
    th = float(e.get('label_h', 20))
    n = {'x': mx - tw / 2, 'y': my - th / 2 - 2, 'w': tw, 'h': th,
         'text': e['text'], 'fs': e.get('label_fs', 9), 'shape': 'rect'}
    x, y, w, h = px(n['x']), px(n['y']), px(n['w']), px(n['h'])
    body = _txbx_content(n['text'], int(float(n['fs']) * 2), 'center', '5F5E5A')
    return f'''<wps:wsp>
<wps:cNvSpPr txBox="1"/>
<wps:spPr>
<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
<a:noFill/><a:ln><a:noFill/></a:ln>
</wps:spPr>
<wps:txbx><w:txbxContent>{body}</w:txbxContent></wps:txbx>
<wps:bodyPr rot="0" vert="horz" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/>
</wps:wsp>'''


def _drawingml_group(fig, docpr_id):
    W, H = px(fig['width']), px(fig['height'])
    parts = [_wsp_edge(e) for e in fig.get('edges', [])]
    parts += [_wsp_edge_label(e) for e in fig.get('edges', [])]
    parts += [_wsp_node(n) for n in fig.get('nodes', [])]
    inner = ''.join(parts)
    return f'''<w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{W}" cy="{H}"/>
<wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="{docpr_id}" name="{esc(fig.get('name', 'Figure'))}" descr="{esc(fig.get('name', ''))}"/>
<wp:cNvGraphicFramePr/>
<a:graphic>
<a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup">
<wpg:wgp>
<wpg:cNvGrpSpPr/><wpg:grpSpPr>
<a:xfrm><a:off x="0" y="0"/><a:ext cx="{W}" cy="{H}"/><a:chOff x="0" y="0"/><a:chExt cx="{W}" cy="{H}"/></a:xfrm>
</wpg:grpSpPr>
{inner}
</wpg:wgp>
</a:graphicData>
</a:graphic>
</wp:inline>
</w:drawing>'''


# ---------------------------------------------------------------- VML fallback
def _vml_group(fig):
    W, H = float(fig['width']), float(fig['height'])
    out = []
    for n in fig.get('nodes', []):
        fill, line = _node_colors(n)
        txt = _txbx_content(n.get('text', ''), int(float(n.get('fs', 10)) * 2))
        out.append(
            f'<v:roundrect style="position:absolute;left:{n["x"]}pt;top:{n["y"]}pt;'
            f'width:{n["w"]}pt;height:{n["h"]}pt" arcsize="12%" '
            f'fillcolor="{fill}" strokecolor="{line}" strokeweight="0.75pt">'
            f'<v:textbox inset="2pt,1pt,2pt,1pt"><w:txbxContent>{txt}</w:txbxContent></v:textbox>'
            f'</v:roundrect>'
        )
    for e in fig.get('edges', []):
        color = e.get('line', '5F5E5A').lstrip('#')
        ar = ' endarrow="block"' if e.get('arrow', True) else ''
        dash = ' dashstyle="dash"' if e.get('dashed') else ''
        out.append(
            f'<v:line from="{e["x1"]},{e["y1"]}" to="{e["x2"]},{e["y2"]}" '
            f'strokecolor="{color}" strokeweight="1pt"{dash}>'
            f'<v:stroke{ar}/></v:line>'
        )
    return (f'<v:group style="width:{W}pt;height:{H}pt" coordorigin="0,0" '
            f'coordsize="{W},{H}">' + ''.join(out) + '</v:group>')


MAX_FIG_W = 600  # px；A4 版心约 16.2cm ≈ 600px
MAX_FIG_H = 780  # px；约 20.6cm，留出图题与段前段后空间，保证单页内放得下


def normalize_fig(fig):
    """兜底：图形超宽或超高时等比缩放；字号同步缩放（不低于 7pt），避免文字溢出形状"""
    w = float(fig.get('width', 0))
    h = float(fig.get('height', 0))
    k = min(MAX_FIG_W / w if w else 1.0,
            MAX_FIG_H / h if h else 1.0, 1.0)
    if k >= 0.999:
        return fig
    fk = max(0.7, k)
    nf = dict(fig)
    nf['width'] = int(round(w * k))
    nf['height'] = int(round(h * k))
    nf['nodes'] = [dict(n, x=round(n['x'] * k, 1), y=round(n['y'] * k, 1),
                        w=round(n['w'] * k, 1), h=round(n['h'] * k, 1),
                        fs=round(float(n.get('fs', 10)) * fk, 1))
                   for n in fig.get('nodes', [])]
    nf['edges'] = []
    for e in fig.get('edges', []):
        ne = dict(e)
        for key in ('x1', 'y1', 'x2', 'y2'):
            if key in ne:
                ne[key] = round(ne[key] * k, 1)
        if ne.get('text'):
            ne['label_fs'] = round(float(e.get('label_fs', 9)) * fk, 1)
            ne['label_w'] = round(float(e.get('label_w', 88)) * k, 1)
        nf['edges'].append(ne)
    return nf


def figure_xml(fig, docpr_id):
    """返回可直接嵌入 w:r 的 mc:AlternateContent 元素"""
    fig = normalize_fig(fig)
    choice = _drawingml_group(fig, docpr_id)
    fallback = _vml_group(fig)
    raw = (f'<mc:AlternateContent {NSDECL}>'
           f'<mc:Choice Requires="wps">{choice}</mc:Choice>'
           f'<mc:Fallback><w:pict>{fallback}</w:pict></mc:Fallback>'
           f'</mc:AlternateContent>')
    return parse_xml(raw)


# ---------------------------------------------------------------- draw.io
def drawio_xml(fig):
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for n in fig.get('nodes', []):
        fill, line = _node_colors(n)
        style = (f'rounded=1;whiteSpace=wrap;html=1;arcSize=12;'
                 f'fillColor={fill};strokeColor={line};fontColor=#2C2C2A;'
                 f'fontSize={int(float(n.get("fs", 10)) + 2)};align=center;verticalAlign=middle;')
        # html=1 时 draw.io 用 <br> 渲染节点内换行，属性值中需写成 &lt;br&gt;
        value = esc(n.get('text', '')).replace('\n', '&lt;br&gt;')
        cells.append(
            f'<mxCell id="{esc(n["id"])}" value="{value}" '
            f'style="{esc(style)}" vertex="1" parent="1">'
            f'<mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/>'
            f'</mxCell>'
        )
    for i, e in enumerate(fig.get('edges', [])):
        style = ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                 'endArrow=block;endFill=1;strokeColor=#5F5E5A;fontColor=#5F5E5A;'
                 'fontSize=10;labelBackgroundColor=#FFFFFF;')
        if e.get('dashed'):
            style += 'dashed=1;'
        cells.append(
            f'<mxCell id="edge-{i}" value="{esc(e.get("text", ""))}" '
            f'style="{esc(style)}" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<Array as="points"/>'
            f'<mxPoint x="{e["x1"]}" y="{e["y1"]}" as="sourcePoint"/>'
            f'<mxPoint x="{e["x2"]}" y="{e["y2"]}" as="targetPoint"/>'
            f'</mxGeometry></mxCell>'
        )
    W, H = int(fig['width']), int(fig['height'])
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<mxfile host="app.diagrams.net" agent="VPP-DocGen" version="21.0.0" '
            f'type="device"><diagram id="{esc(fig["id"])}" name="{esc(fig.get("name", "Figure"))}">'
            f'<mxGraphModel dx="1100" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{W + 80}" pageHeight="{H + 80}" math="0" shadow="0">'
            f'<root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')


# ---------------------------------------------------------------- DOCX 排版
def _set_styles(doc):
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0x2C, 0x2C, 0x2A)
    rpr = normal._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), '微软雅黑')
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.35
    for name, size, color in [('Title', 26, 0x1A3A5C), ('Heading 1', 18, 0x185FA5),
                              ('Heading 2', 14, 0x0F6E56), ('Heading 3', 12, 0x2C2C2A)]:
        try:
            st = doc.styles[name]
            st.font.name = 'Calibri'
            st.font.size = Pt(size)
            st.font.color.rgb = RGBColor((color >> 16) & 255, (color >> 8) & 255, color & 255)
            st.font.bold = True
            rf = st._element.get_or_add_rPr().find(qn('w:rFonts'))
            if rf is None:
                rf = OxmlElement('w:rFonts')
                st._element.get_or_add_rPr().append(rf)
            rf.set(qn('w:eastAsia'), '微软雅黑')
        except KeyError:
            pass
    for sec in doc.sections:
        sec.top_margin = Cm(2.2)
        sec.bottom_margin = Cm(2.2)
        sec.left_margin = Cm(2.4)
        sec.right_margin = Cm(2.4)


def _shade(paragraph, fill):
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    ppr.append(shd)


CODE_LABELS = {
    'bash': '命令示例 · Shell', 'sh': '命令示例 · Shell', 'shell': '命令示例 · Shell',
    'c': '代码片段 · C', 'cpp': '代码片段 · C++',
    'ini': '配置片段 · startup.conf', 'conf': '配置片段',
    'yaml': '配置片段 · YAML', 'yml': '配置片段 · YAML',
    'python': '代码片段 · Python', 'py': '代码片段 · Python',
    'dockerfile': 'Dockerfile',
    'json': '数据片段 · JSON', 'text': '输出 / 文本示例', 'tree': '目录结构',
}


def _add_code(doc, text, lang=None):
    label = CODE_LABELS.get((lang or 'text').lower(), '示例 · ' + str(lang or 'text'))
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(label)
    r.font.size = Pt(8)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x7A, 0x78, 0x72)
    for i, line in enumerate(str(text).split('\n')):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.4)
        _shade(p, 'F1EFE8')
        r = p.add_run(line if line else ' ')
        r.font.name = 'Consolas'
        r.font.size = Pt(9)
        rpr = r._element.get_or_add_rPr()
        rf = rpr.find(qn('w:rFonts'))
        if rf is None:
            rf = OxmlElement('w:rFonts')
            rpr.append(rf)
        rf.set(qn('w:eastAsia'), '等线')
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _add_table(doc, header, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False  # 固定布局，下面按内容长度分配列宽

    def _cell_style(cell, text, bold=False):
        cell.text = ''
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(str(text))
        r.bold = bold
        r.font.size = Pt(9)
        return p

    hdr = t.rows[0].cells
    for i, h in enumerate(header):
        _cell_style(hdr[i], h, bold=True)
        tcpr = hdr[i]._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), 'E6F1FB')
        tcpr.append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row[:len(header)]):
            _cell_style(cells[i], v)

    # 长表格跨页时重复表头；任一行都不被拆到两页
    trpr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement('w:tblHeader')
    th.set(qn('w:val'), 'true')
    trpr.append(th)
    for row in t.rows:
        cs = OxmlElement('w:cantSplit')
        row._tr.get_or_add_trPr().append(cs)

    # 按各列内容的平均显示长度分配版心宽度：文字多的列更宽，短编号列更窄
    if not widths:
        def dlen(s):
            return sum(2 if ord(c) > 127 else 1 for c in str(s))

        sec = doc.sections[0]
        avail = (sec.page_width - sec.left_margin - sec.right_margin) / 360000.0
        n = len(header)
        weights = []
        for j in range(n):
            vals = [dlen(header[j])] + [dlen(r[j]) for r in rows if j < len(r)]
            avg = sum(vals) / max(1, len(vals))
            weights.append(max(6.0, min(28.0, avg ** 0.65)))
        total = sum(weights)
        widths = [avail * w / total for w in weights]
    for row in t.rows:
        for i, w in enumerate(widths[:len(header)]):
            row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def _add_figure(doc, fig, caption, figures_dir, docpr_id, manifest):
    fig = normalize_fig(fig)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run()
    r._r.append(figure_xml(fig, docpr_id))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run(caption)
    cr.font.size = Pt(9)
    cr.font.color.rgb = RGBColor(0x5F, 0x5E, 0x5A)
    cap.paragraph_format.space_after = Pt(10)

    safe = ''.join(c if c not in '\\/:*?"<>|' else '_' for c in fig.get('name', fig['id']))
    fname = f"{fig['id']}_{safe}.drawio"
    fpath = os.path.join(figures_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(drawio_xml(fig))
    manifest.append({'id': fig['id'], 'name': fig.get('name', ''),
                     'docx_figure': 'DrawingML group shape (editable)',
                     'drawio': fpath, 'caption': caption})


def build_docx(spec, out_path, figures_dir=None):
    """spec: {'title','subtitle','meta':[...],'blocks':[...]}"""
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    if figures_dir:
        os.makedirs(os.path.abspath(figures_dir), exist_ok=True)
    doc = Document()
    _set_styles(doc)
    manifest = []
    docpr_id = 1000

    tp = doc.add_paragraph(style='Title')
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp.add_run(spec['title'])
    if spec.get('subtitle'):
        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sr = sp.add_run(spec['subtitle'])
        sr.font.size = Pt(12)
        sr.font.color.rgb = RGBColor(0x5F, 0x5E, 0x5A)
    if spec.get('meta'):
        mp = doc.add_paragraph()
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mr = mp.add_run('  |  '.join(spec['meta']))
        mr.font.size = Pt(9)
        mr.font.color.rgb = RGBColor(0x88, 0x87, 0x80)
    doc.add_paragraph()

    for b in spec['blocks']:
        t = b.get('t')
        if t == 'h1':
            doc.add_heading(b['text'], level=1)
        elif t == 'h2':
            doc.add_heading(b['text'], level=2)
        elif t == 'h3':
            doc.add_heading(b['text'], level=3)
        elif t == 'p':
            doc.add_paragraph(b['text'])
        elif t == 'bullets':
            for it in b['items']:
                doc.add_paragraph(str(it), style='List Bullet')
        elif t == 'nums':
            for it in b['items']:
                doc.add_paragraph(str(it), style='List Number')
        elif t == 'code':
            _add_code(doc, b['text'], b.get('lang'))
        elif t == 'table':
            _add_table(doc, b['header'], b['rows'], b.get('widths'))
        elif t == 'note':
            p = doc.add_paragraph()
            _shade(p, b.get('fill', 'FAEEDA'))
            r = p.add_run(b['text'])
            r.font.size = Pt(10)
        elif t == 'figure':
            docpr_id += 1
            _add_figure(doc, b['fig'], b.get('caption', ''), figures_dir or os.path.dirname(out_path),
                        docpr_id, manifest)
        elif t == 'pagebreak':
            doc.add_page_break()

    doc.core_properties.title = spec['title']
    doc.core_properties.subject = 'VPP 技术资料'
    doc.core_properties.author = 'VPP 技术资料项目'
    doc.save(out_path)
    return {'docx': out_path, 'figures': manifest, 'figure_count': len(manifest)}


def edge_between(a, b, side='auto', text='', **kw):
    """由两个节点的相对位置生成水平/垂直连线（保证 DrawingML 直线可编辑）"""
    ax, ay, aw, ah = a['x'], a['y'], a['w'], a['h']
    bx, by, bw, bh = b['x'], b['y'], b['w'], b['h']
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    if side == 'h' or (side == 'auto' and abs(bcy - acy) <= abs(bcx - acx)):
        if bcx >= acx:
            x1, x2 = ax + aw, bx
        else:
            x1, x2 = ax, bx + bw
        y1 = y2 = acy if abs(bcy - acy) < ah else acy
        e = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
        if text:
            e['text'] = text
            e['label_w'] = kw.get('label_w', 88)
            e['label_h'] = kw.get('label_h', 20)
    else:
        if bcy >= acy:
            y1, y2 = ay + ah, by
        else:
            y1, y2 = ay, by + bh
        x1 = x2 = acx if abs(bcx - acx) < aw else acx
        e = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
        if text:
            e['text'] = text
            e['label_w'] = kw.get('label_w', 88)
            e['label_h'] = kw.get('label_h', 20)
    e.update({k: v for k, v in kw.items() if k not in ('label_w', 'label_h')})
    return e


if __name__ == '__main__':
    print('vpp_docgen ready')
