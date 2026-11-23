"""Genera el informe técnico AE4 SIG en formatos DOCX (APA 7 / UCP) y Markdown.

Salidas producidas exclusivamente dentro de `ae4_sig/dock/`:
  - `ae4_sig/dock/AE4_SIG_Sanchez_Nunez.docx`
  - `ae4_sig/dock/AE4_SIG_Sanchez_Nunez.md`

Incluye verificación programática final para garantizar la ausencia absoluta de
términos ajenos al contexto académico universitario en ambos entregables.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
import xml.etree.ElementTree as ET

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

AE4_ROOT = Path(__file__).resolve().parents[1]
DOCK_DIR = AE4_ROOT / "dock"
FIGURAS_DIR = DOCK_DIR / "figuras"
DOCX_PATH = DOCK_DIR / "AE4_SIG_Sanchez_Nunez.docx"
MD_PATH = DOCK_DIR / "AE4_SIG_Sanchez_Nunez.md"

LOGO_PATH = FIGURAS_DIR / "logo_ucp.png"

BLACK = RGBColor(0, 0, 0)
MUTED_GRAY = RGBColor(71, 85, 105)
PRINTABLE_WIDTH_CM = 15.92
MAX_CODE_LINE_LEN = 78

INLINE_TOKEN_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")


# -----------------------------------------------------------------------------
# Utilidades XML / python-docx
# -----------------------------------------------------------------------------


def cm_to_dxa(cm_val: float) -> int:
    """Convierte centímetros a twips (dxa: 1/20 pt, 1440 dxa = 2.54 cm)."""
    return int(round(cm_val * 1440.0 / 2.54))


def set_run_font(
    run,
    *,
    name: str = "Times New Roman",
    size_pt: float = 12.0,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: RGBColor = BLACK,
) -> None:
    """Aplica tipografía explícita en OOXML para compatibilidad Word/LibreOffice."""
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.underline = underline
    run.font.color.rgb = color

    r_pr = run._r.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
        r_fonts.set(qn(f"w:{attr}"), name)


def set_style_font(
    style,
    *,
    name: str = "Times New Roman",
    size_pt: float = 12.0,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor = BLACK,
) -> None:
    """Configura tipografía base en un estilo de párrafo."""
    style.font.name = name
    style.font.size = Pt(size_pt)
    style.font.bold = bold
    style.font.italic = italic
    style.font.color.rgb = color

    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
        r_fonts.set(qn(f"w:{attr}"), name)


def add_inline_runs(
    paragraph,
    text: str,
    *,
    base_size_pt: float = 12.0,
    base_bold: bool = False,
    base_italic: bool = False,
    color: RGBColor = BLACK,
    code_size_pt: float | None = None,
) -> None:
    """Interpreta **negrita**, *cursiva* y `código` (recursivo) sin dejar backticks."""
    resolved_code_size = (
        code_size_pt
        if code_size_pt is not None
        else (10.5 if base_size_pt >= 11.5 else max(8.0, base_size_pt - 1.0))
    )
    pos = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        if match.start() > pos:
            r = paragraph.add_run(text[pos : match.start()])
            set_run_font(
                r,
                name="Times New Roman",
                size_pt=base_size_pt,
                bold=base_bold,
                italic=base_italic,
                color=color,
            )
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            add_inline_runs(
                paragraph,
                token[2:-2],
                base_size_pt=base_size_pt,
                base_bold=True,
                base_italic=base_italic,
                color=color,
                code_size_pt=resolved_code_size,
            )
        elif token.startswith("*") and token.endswith("*"):
            add_inline_runs(
                paragraph,
                token[1:-1],
                base_size_pt=base_size_pt,
                base_bold=base_bold,
                base_italic=True,
                color=color,
                code_size_pt=resolved_code_size,
            )
        elif token.startswith("`") and token.endswith("`"):
            r = paragraph.add_run(token[1:-1])
            set_run_font(
                r,
                name="Times New Roman",
                size_pt=base_size_pt,
                bold=base_bold,
                italic=base_italic,
                color=color,
            )
        pos = match.end()

    if pos < len(text):
        r = paragraph.add_run(text[pos:])
        set_run_font(
            r,
            name="Times New Roman",
            size_pt=base_size_pt,
            bold=base_bold,
            italic=base_italic,
            color=color,
        )


def add_page_number_field(paragraph) -> None:
    """Inserta un campo nativo PAGE de Word en Times New Roman 11 pt negro."""
    r_begin = paragraph.add_run()
    set_run_font(r_begin, size_pt=11.0)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    r_begin._r.append(fld_begin)

    r_instr = paragraph.add_run()
    set_run_font(r_instr, size_pt=11.0)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    r_instr._r.append(instr)

    r_sep = paragraph.add_run()
    set_run_font(r_sep, size_pt=11.0)
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep._r.append(fld_sep)

    r_val = paragraph.add_run("2")
    set_run_font(r_val, size_pt=11.0)

    r_end = paragraph.add_run()
    set_run_font(r_end, size_pt=11.0)
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end._r.append(fld_end)


def add_toc_field(doc: Document) -> None:
    """Inserta un campo TOC nativo (`TOC \\o "1-3" \\h \\z \\u`) actualizable en Word."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    r_begin = p.add_run()
    set_run_font(r_begin, size_pt=11.0)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    fld_begin.set(qn("w:dirty"), "true")
    r_begin._r.append(fld_begin)

    r_instr = p.add_run()
    set_run_font(r_instr, size_pt=11.0)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    r_instr._r.append(instr)

    r_sep = p.add_run()
    set_run_font(r_sep, size_pt=11.0)
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r_sep._r.append(fld_sep)

    r_hint = p.add_run(
        "Haga clic derecho sobre este bloque y seleccione «Actualizar campos» "
        "en Microsoft Word para poblar el índice con la numeración exacta de páginas."
    )
    set_run_font(r_hint, size_pt=11.0, italic=True, color=MUTED_GRAY)

    r_end = p.add_run()
    set_run_font(r_end, size_pt=11.0)
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r_end._r.append(fld_end)


def enable_update_fields_on_open(doc: Document) -> None:
    """Habilita `<w:updateFields w:val="true"/>` en settings.xml."""
    settings_el = doc.settings.element
    existing = settings_el.find(qn("w:updateFields"))
    if existing is None:
        el = OxmlElement("w:updateFields")
        el.set(qn("w:val"), "true")
        settings_el.append(el)
    else:
        existing.set(qn("w:val"), "true")


def configure_document() -> Document:
    """Inicializa página A4, márgenes 2,54 cm, numeración desde pág. 2 y estilos APA 7."""
    doc = Document()
    enable_update_fields_on_open(doc)

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.header_distance = Cm(1.27)
    section.footer_distance = Cm(1.27)
    section.different_first_page_header_footer = True

    # Limpiar encabezado de portada (página 1)
    first_hdr = section.first_page_header
    first_hdr.paragraphs[0].text = ""

    # Encabezado desde página 2: número de página a la derecha, Times New Roman 11 pt
    hdr = section.header
    hp = hdr.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.paragraph_format.first_line_indent = Cm(0)
    hp.paragraph_format.space_before = Pt(0)
    hp.paragraph_format.space_after = Pt(0)
    add_page_number_field(hp)

    # Estilo Normal
    normal = doc.styles["Normal"]
    set_style_font(normal, name="Times New Roman", size_pt=12.0, color=BLACK)
    npf = normal.paragraph_format
    npf.line_spacing = 2.0
    npf.space_before = Pt(0)
    npf.space_after = Pt(0)
    npf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    npf.first_line_indent = Cm(1.27)

    # Heading 1 — centrado, negrita, Times New Roman 12 pt, salto de página previo
    h1 = doc.styles["Heading 1"]
    set_style_font(h1, name="Times New Roman", size_pt=12.0, bold=True, color=BLACK)
    h1_pf = h1.paragraph_format
    h1_pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1_pf.first_line_indent = Cm(0)
    h1_pf.space_before = Pt(0)
    h1_pf.space_after = Pt(12)
    h1_pf.line_spacing = 2.0
    h1_pf.keep_with_next = True
    h1_pf.page_break_before = True

    # Heading 2 — izquierda, negrita, Times New Roman 12 pt
    h2 = doc.styles["Heading 2"]
    set_style_font(h2, name="Times New Roman", size_pt=12.0, bold=True, color=BLACK)
    h2_pf = h2.paragraph_format
    h2_pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h2_pf.first_line_indent = Cm(0)
    h2_pf.space_before = Pt(12)
    h2_pf.space_after = Pt(6)
    h2_pf.line_spacing = 2.0
    h2_pf.keep_with_next = True

    # Heading 3 — izquierda, negrita + cursiva, Times New Roman 12 pt
    h3 = doc.styles["Heading 3"]
    set_style_font(
        h3, name="Times New Roman", size_pt=12.0, bold=True, italic=True, color=BLACK
    )
    h3_pf = h3.paragraph_format
    h3_pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    h3_pf.first_line_indent = Cm(0)
    h3_pf.space_before = Pt(6)
    h3_pf.space_after = Pt(4)
    h3_pf.line_spacing = 2.0
    h3_pf.keep_with_next = True

    # Estilos integrados TOC1..TOC3 (styleId exacto sin customStyle para Word TOC)
    for level, left_cm in ((1, 0.0), (2, 0.5), (3, 1.0)):
        style_name = f"toc {level}"
        try:
            toc_st = doc.styles[style_name]
        except KeyError:
            toc_st = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        toc_st.element.set(qn("w:styleId"), f"TOC{level}")
        toc_st.element.attrib.pop(qn("w:customStyle"), None)
        toc_st.base_style = normal
        set_style_font(toc_st, name="Times New Roman", size_pt=12.0, color=BLACK)
        tpf = toc_st.paragraph_format
        tpf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        tpf.first_line_indent = Cm(0)
        tpf.left_indent = Cm(left_cm)
        tpf.space_before = Pt(0)
        tpf.space_after = Pt(2)
        tpf.line_spacing = 1.35

    return doc


def _set_cell_borders(cell, *, top: str | None, bottom: str | None) -> None:
    """Configura bordes APA 7 en una celda (solo horizontales especificados)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:tcBorders"))
    if existing is not None:
        tc_pr.remove(existing)

    top_xml = (
        f'<w:top w:val="single" w:sz="{top}" w:space="0" w:color="000000"/>'
        if top
        else '<w:top w:val="nil"/>'
    )
    bot_xml = (
        f'<w:bottom w:val="single" w:sz="{bottom}" w:space="0" w:color="000000"/>'
        if bottom
        else '<w:bottom w:val="nil"/>'
    )
    borders_xml = (
        f"<w:tcBorders {nsdecls('w')}>"
        f"{top_xml}"
        '<w:left w:val="nil"/>'
        f"{bot_xml}"
        '<w:right w:val="nil"/>'
        "</w:tcBorders>"
    )
    tc_pr.append(parse_xml(borders_xml))


def _set_cell_margins(
    cell, *, top: int = 55, bottom: int = 55, left: int = 70, right: int = 70
) -> None:
    """Configura márgenes internos compactos en dxa."""
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:tcMar"))
    if existing is not None:
        tc_pr.remove(existing)
    mar_xml = (
        f"<w:tcMar {nsdecls('w')}>"
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        "</w:tcMar>"
    )
    tc_pr.append(parse_xml(mar_xml))


def _set_cell_width_dxa(cell, width_cm: float) -> None:
    """Fija el ancho exacto de celda en dxa."""
    dxa = cm_to_dxa(width_cm)
    tc_pr = cell._tc.get_or_add_tcPr()
    existing = tc_pr.find(qn("w:tcW"))
    if existing is not None:
        tc_pr.remove(existing)
    tc_w = OxmlElement("w:tcW")
    tc_w.set(qn("w:w"), str(dxa))
    tc_w.set(qn("w:type"), "dxa")
    tc_pr.append(tc_w)


def add_apa_table(
    doc: Document,
    num: int,
    title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    col_widths_cm: Sequence[float],
    col_alignments: Sequence[WD_ALIGN_PARAGRAPH],
    note: str,
    body_font_pt: float = 9.0,
    cell_pad_lr_dxa: int = 70,
) -> None:
    """Agrega una tabla estrictamente formateada según APA 7."""
    total_w = sum(col_widths_cm)
    assert total_w <= PRINTABLE_WIDTH_CM + 0.01, (
        f"Tabla {num}: ancho total {total_w:.2f} cm supera {PRINTABLE_WIDTH_CM} cm"
    )
    assert len(headers) == len(col_widths_cm) == len(col_alignments)

    p_num = doc.add_paragraph()
    p_num.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_num.paragraph_format.first_line_indent = Cm(0)
    p_num.paragraph_format.space_before = Pt(6)
    p_num.paragraph_format.space_after = Pt(0)
    p_num.paragraph_format.line_spacing = 1.15
    p_num.paragraph_format.keep_with_next = True
    r_num = p_num.add_run(f"Tabla {num}")
    set_run_font(r_num, size_pt=12.0, bold=True)

    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_tit.paragraph_format.first_line_indent = Cm(0)
    p_tit.paragraph_format.space_before = Pt(0)
    p_tit.paragraph_format.space_after = Pt(4)
    p_tit.paragraph_format.line_spacing = 1.15
    p_tit.paragraph_format.keep_with_next = True
    add_inline_runs(p_tit, title, base_size_pt=12.0, base_italic=True, code_size_pt=10.5)

    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl.autofit = False

    # Propiedades de tabla: ancho fijo, layout fixed, bordes horizontales APA 7
    tbl_pr = tbl._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout", "w:tblBorders"):
        el = tbl_pr.find(qn(tag))
        if el is not None:
            tbl_pr.remove(el)

    tbl_pr.append(
        parse_xml(f'<w:tblW {nsdecls("w")} w:w="{cm_to_dxa(total_w)}" w:type="dxa"/>')
    )
    tbl_pr.append(parse_xml(f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))
    tbl_pr.append(
        parse_xml(
            f"<w:tblBorders {nsdecls('w')}>"
            '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            '<w:left w:val="nil"/>'
            '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            '<w:right w:val="nil"/>'
            '<w:insideH w:val="nil"/>'
            '<w:insideV w:val="nil"/>'
            "</w:tblBorders>"
        )
    )

    # Reemplazar tblGrid con anchos exactos
    old_grid = tbl._tbl.find(qn("w:tblGrid"))
    if old_grid is not None:
        tbl._tbl.remove(old_grid)
    new_grid = OxmlElement("w:tblGrid")
    for w_cm in col_widths_cm:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(cm_to_dxa(w_cm)))
        new_grid.append(gc)
    tbl_pr.addnext(new_grid)

    # Fila de encabezado
    hdr_row = tbl.rows[0]
    hdr_tr_pr = hdr_row._tr.get_or_add_trPr()
    hdr_tr_pr.append(OxmlElement("w:tblHeader"))
    hdr_tr_pr.append(OxmlElement("w:cantSplit"))

    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_width_dxa(cell, col_widths_cm[c_idx])
        _set_cell_margins(cell, top=55, bottom=55, left=cell_pad_lr_dxa, right=cell_pad_lr_dxa)
        _set_cell_borders(cell, top="8", bottom="6")
        cp = cell.paragraphs[0]
        cp.alignment = col_alignments[c_idx]
        cp.paragraph_format.first_line_indent = Cm(0)
        cp.paragraph_format.space_before = Pt(0)
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.line_spacing = 1.15
        cp.paragraph_format.keep_with_next = True
        add_inline_runs(cp, h_text, base_size_pt=9.5, base_bold=True, code_size_pt=8.5)

    # Filas del cuerpo
    last_idx = len(rows) - 1
    for r_idx, row_vals in enumerate(rows):
        assert len(row_vals) == len(headers), (
            f"Tabla {num} fila {r_idx}: columnas esperadas={len(headers)}, obtenidas={len(row_vals)}"
        )
        row = tbl.rows[r_idx + 1]
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        is_last = r_idx == last_idx
        bot_border = "8" if is_last else None

        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _set_cell_width_dxa(cell, col_widths_cm[c_idx])
            _set_cell_margins(cell, top=55, bottom=55, left=cell_pad_lr_dxa, right=cell_pad_lr_dxa)
            _set_cell_borders(cell, top=None, bottom=bot_border)
            cp = cell.paragraphs[0]
            cp.alignment = col_alignments[c_idx]
            cp.paragraph_format.first_line_indent = Cm(0)
            cp.paragraph_format.space_before = Pt(0)
            cp.paragraph_format.space_after = Pt(0)
            cp.paragraph_format.line_spacing = 1.15
            if is_last:
                # Mantener la última fila unida a la Nota para evitar notas huérfanas
                cp.paragraph_format.keep_with_next = True
            add_inline_runs(cp, str(val), base_size_pt=body_font_pt, code_size_pt=8.5)

    # Nota de tabla
    p_note = doc.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_note.paragraph_format.first_line_indent = Cm(0)
    p_note.paragraph_format.space_before = Pt(4)
    p_note.paragraph_format.space_after = Pt(12)
    p_note.paragraph_format.line_spacing = 1.3
    r_lbl = p_note.add_run("Nota. ")
    set_run_font(r_lbl, size_pt=10.5, italic=True)
    add_inline_runs(p_note, note, base_size_pt=10.5, code_size_pt=9.5)


def add_figure(
    doc: Document,
    num: int,
    img_path: Path,
    caption_desc: str,
    source_note: str,
    width_cm: float = 15.4,
) -> None:
    """Inserta figura centrada (con keep_with_next) y leyenda APA debajo."""
    assert img_path.exists(), f"Figura no encontrada: {img_path}"

    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.first_line_indent = Cm(0)
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.line_spacing = 1.0
    p_img.paragraph_format.keep_with_next = True
    p_img.add_run().add_picture(str(img_path), width=Cm(width_cm))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.first_line_indent = Cm(0)
    p_cap.paragraph_format.space_before = Pt(4)
    p_cap.paragraph_format.space_after = Pt(12)
    p_cap.paragraph_format.line_spacing = 1.3

    r_fig = p_cap.add_run(f"Figura {num}. ")
    set_run_font(r_fig, size_pt=10.5, bold=True)
    add_inline_runs(
        p_cap, f"{caption_desc} ", base_size_pt=10.5, base_italic=True, code_size_pt=9.5
    )
    add_inline_runs(p_cap, f"{source_note} Elaboración propia.", base_size_pt=10.5, code_size_pt=9.5)


def add_code_block(doc: Document, code_str: str) -> None:
    """Agrega un bloque de código sombreado en Courier New 9,5 pt sin desbordes."""
    lines = code_str.strip("\n").splitlines()
    for idx, ln in enumerate(lines, 1):
        assert len(ln) <= MAX_CODE_LINE_LEN, (
            f"Línea de código {idx} excede {MAX_CODE_LINE_LEN} caracteres ({len(ln)}): {ln}"
        )

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.left_indent = Cm(0.3)
    pf.right_indent = Cm(0.3)
    pf.space_before = Pt(4)
    pf.space_after = Pt(8)
    pf.line_spacing = 1.15
    pf.keep_together = True

    p_pr = p._p.get_or_add_pPr()
    p_pr.append(
        parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="F4F6F8"/>')
    )
    p_pr.append(
        parse_xml(
            f"<w:pBdr {nsdecls('w')}>"
            '<w:left w:val="single" w:sz="18" w:space="6" w:color="334155"/>'
            '<w:top w:val="none"/>'
            '<w:right w:val="none"/>'
            '<w:bottom w:val="none"/>'
            "</w:pBdr>"
        )
    )

    r = p.add_run("\n".join(lines))
    set_run_font(r, name="Times New Roman", size_pt=9.5, color=BLACK)


# -----------------------------------------------------------------------------
# Constructor dual DOCX + Markdown sincronizado
# -----------------------------------------------------------------------------


class ReportBuilder:
    """Sincroniza la construcción del informe en formato DOCX y Markdown."""

    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.md: List[str] = []
        self.table_registry: List[Tuple[int, str]] = []

    def add_cover(self) -> None:
        """Genera la portada institucional UCP (Página 1) y su cabecera en MD."""
        assert LOGO_PATH.exists(), f"Logo UCP no encontrado: {LOGO_PATH}"

        p_logo = self.doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.first_line_indent = Cm(0)
        p_logo.paragraph_format.space_before = Pt(0)
        p_logo.paragraph_format.space_after = Pt(18)
        p_logo.paragraph_format.line_spacing = 1.0
        p_logo.add_run().add_picture(str(LOGO_PATH), width=Cm(8.5))

        header_lines = [
            ("UNIVERSIDAD DE LA CUENCA DEL PLATA", True, False),
            ("Facultad de Ingeniería, Tecnología y Arquitectura", True, False),
            ("Ingeniería en Sistemas de Información", True, False),
            ("Sistemas de Información Geográfica", True, False),
            ("Actividad de Evaluación 4 (AE4)", True, True),
        ]
        for text, bold, underline in header_lines:
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.5
            r = p.add_run(text)
            set_run_font(r, size_pt=12.0, bold=bold, underline=underline)

        p_sede = self.doc.add_paragraph()
        p_sede.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_sede.paragraph_format.first_line_indent = Cm(0)
        p_sede.paragraph_format.space_before = Pt(4)
        p_sede.paragraph_format.space_after = Pt(0)
        p_sede.paragraph_format.line_spacing = 1.5
        r_sede = p_sede.add_run("Sede Posadas")
        set_run_font(r_sede, size_pt=12.0)

        meta_items = [
            ("Autores:", " Sánchez, Joaquín Sebastián; Nuñez, Santiago Agustín"),
            ("DNI:", " 45.452.416; 44.952.958"),
            ("Profesor:", " Edgar Rolando Ibáñez"),
            ("Fecha de entrega:", " 23 de noviembre de 2026"),
        ]
        for idx, (lbl, val) in enumerate(meta_items):
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_before = Pt(36 if idx == 0 else 0)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.8
            r1 = p.add_run(lbl)
            set_run_font(r1, size_pt=12.0, bold=True, underline=True)
            r2 = p.add_run(val)
            set_run_font(r2, size_pt=12.0)

        p_year = self.doc.add_paragraph()
        p_year.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_year.paragraph_format.first_line_indent = Cm(0)
        p_year.paragraph_format.space_before = Pt(42)
        p_year.paragraph_format.space_after = Pt(0)
        p_year.paragraph_format.line_spacing = 1.5
        r_y1 = p_year.add_run("AÑO:")
        set_run_font(r_y1, size_pt=12.0, bold=True, underline=True)
        r_y2 = p_year.add_run(" 2026")
        set_run_font(r_y2, size_pt=12.0)

        # Portada en Markdown
        self.md.extend(
            [
                "# UNIVERSIDAD DE LA CUENCA DEL PLATA",
                "**Facultad de Ingeniería, Tecnología y Arquitectura**  ",
                "**Ingeniería en Sistemas de Información**  ",
                "**Sistemas de Información Geográfica**  ",
                "**Actividad de Evaluación 4 (AE4)**  ",
                "Sede Posadas",
                "",
                "- **Autores:** Sánchez, Joaquín Sebastián; Nuñez, Santiago Agustín",
                "- **DNI:** 45.452.416; 44.952.958",
                "- **Profesor:** Edgar Rolando Ibáñez",
                "- **Fecha de entrega:** 23 de noviembre de 2026",
                "- **AÑO:** 2026",
                "",
                "---",
                "",
            ]
        )

    def add_toc_placeholder(self) -> None:
        """Agrega página de Índice general (campo Word) e Índice de tablas."""
        p_title = self.doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title.paragraph_format.first_line_indent = Cm(0)
        p_title.paragraph_format.page_break_before = True
        p_title.paragraph_format.space_before = Pt(0)
        p_title.paragraph_format.space_after = Pt(12)
        p_title.paragraph_format.line_spacing = 1.5
        p_title.paragraph_format.keep_with_next = True
        r_t = p_title.add_run("Índice general")
        set_run_font(r_t, size_pt=12.0, bold=True)

        add_toc_field(self.doc)

        p_tbl_title = self.doc.add_paragraph()
        p_tbl_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_tbl_title.paragraph_format.first_line_indent = Cm(0)
        p_tbl_title.paragraph_format.page_break_before = True
        p_tbl_title.paragraph_format.space_before = Pt(0)
        p_tbl_title.paragraph_format.space_after = Pt(8)
        p_tbl_title.paragraph_format.line_spacing = 1.5
        p_tbl_title.paragraph_format.keep_with_next = True
        r_tt = p_tbl_title.add_run("Índice de tablas")
        set_run_font(r_tt, size_pt=12.0, bold=True)

        self.toc_tables_anchor = p_tbl_title

    def populate_table_index(self) -> None:
        """Inserta la lista compacta de Tabla 1..13 debajo de 'Índice de tablas'."""
        anchor = self.toc_tables_anchor
        # Insertar párrafos justo después de anchor en orden inverso para usar addnext
        for num, title in reversed(self.table_registry):
            p = OxmlElement("w:p")
            p_pr = OxmlElement("w:pPr")
            spacing = OxmlElement("w:spacing")
            spacing.set(qn("w:before"), "0")
            spacing.set(qn("w:after"), "40")
            spacing.set(qn("w:line"), "324")
            spacing.set(qn("w:lineRule"), "auto")
            p_pr.append(spacing)
            ind = OxmlElement("w:ind")
            ind.set(qn("w:firstLine"), "0")
            p_pr.append(ind)
            jc = OxmlElement("w:jc")
            jc.set(qn("w:val"), "left")
            p_pr.append(jc)
            p.append(p_pr)

            r1 = OxmlElement("w:r")
            r1_pr = OxmlElement("w:rPr")
            r1_fonts = OxmlElement("w:rFonts")
            for a in ("ascii", "hAnsi", "cs", "eastAsia"):
                r1_fonts.set(qn(f"w:{a}"), "Times New Roman")
            r1_pr.append(r1_fonts)
            r1_pr.append(OxmlElement("w:b"))
            sz1 = OxmlElement("w:sz")
            sz1.set(qn("w:val"), "24")
            sz1_cs = OxmlElement("w:szCs")
            sz1_cs.set(qn("w:val"), "24")
            r1_pr.append(sz1)
            r1_pr.append(sz1_cs)
            r1.append(r1_pr)
            t1 = OxmlElement("w:t")
            t1.set(qn("xml:space"), "preserve")
            t1.text = f"Tabla {num}. "
            r1.append(t1)
            p.append(r1)

            r2 = OxmlElement("w:r")
            r2_pr = OxmlElement("w:rPr")
            r2_fonts = OxmlElement("w:rFonts")
            for a in ("ascii", "hAnsi", "cs", "eastAsia"):
                r2_fonts.set(qn(f"w:{a}"), "Times New Roman")
            r2_pr.append(r2_fonts)
            sz2 = OxmlElement("w:sz")
            sz2.set(qn("w:val"), "24")
            sz2_cs = OxmlElement("w:szCs")
            sz2_cs.set(qn("w:val"), "24")
            r2_pr.append(sz2)
            r2_pr.append(sz2_cs)
            r2.append(r2_pr)
            t2 = OxmlElement("w:t")
            t2.text = title
            r2.append(t2)
            p.append(r2)

            anchor._p.addnext(p)

        # Insertar índice general y de tablas en Markdown justo después de portada
        toc_md = [
            "## Índice general",
            "1. Introducción",
            "2. Fuentes de datos y arquitectura tecnológica",
            "3. Fase I: Diseño e implementación de la base de datos espacial",
            "4. Fase II: Consultas espaciales y optimización con índices GiST",
            "5. Fase III: Interoperabilidad cliente-servidor con QGIS 4.2.1",
            "6. Conclusiones",
            "7. Portafolio digital",
            "8. Índice de figuras",
            "9. Referencias",
            "",
            "## Índice de tablas",
        ]
        for num, title in self.table_registry:
            toc_md.append(f"- **Tabla {num}.** {title}")
        toc_md.extend(["", "---", ""])

        # Ubicar tras el primer separador '---'
        sep_idx = self.md.index("---")
        self.md = self.md[: sep_idx + 2] + toc_md + self.md[sep_idx + 2 :]

    def h1(self, title: str) -> None:
        p = self.doc.add_paragraph(style="Heading 1")
        add_inline_runs(p, title, base_size_pt=12.0, base_bold=True)
        self.md.extend([f"## {title}", ""])

    def h2(self, title: str) -> None:
        p = self.doc.add_paragraph(style="Heading 2")
        add_inline_runs(p, title, base_size_pt=12.0, base_bold=True)
        self.md.extend([f"### {title}", ""])

    def h3(self, title: str) -> None:
        p = self.doc.add_paragraph(style="Heading 3")
        add_inline_runs(p, title, base_size_pt=12.0, base_bold=True, base_italic=True)
        self.md.extend([f"#### {title}", ""])

    def p(
        self,
        text: str,
        alignment: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.JUSTIFY,
    ) -> None:
        par = self.doc.add_paragraph(style="Normal")
        par.alignment = alignment
        add_inline_runs(par, text, base_size_pt=12.0)
        self.md.extend([text, ""])

    def bullets(
        self,
        items: Sequence[str],
        alignment: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.JUSTIFY,
    ) -> None:
        for item in items:
            par = self.doc.add_paragraph(style="Normal")
            par.alignment = alignment
            pf = par.paragraph_format
            pf.left_indent = Cm(1.27)
            pf.first_line_indent = Cm(-0.63)
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.line_spacing = 2.0
            pf.tab_stops.add_tab_stop(Cm(1.27), WD_TAB_ALIGNMENT.LEFT)
            r_bul = par.add_run("•\t")
            set_run_font(r_bul, size_pt=12.0)
            add_inline_runs(par, item, base_size_pt=12.0)
            self.md.append(f"- {item}")
        self.md.append("")

    def code(self, code_str: str, lang: str = "sql") -> None:
        add_code_block(self.doc, code_str)
        self.md.extend([f"```{lang}", code_str.strip("\n"), "```", ""])

    def table(
        self,
        num: int,
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        col_widths_cm: Sequence[float],
        col_alignments: Sequence[WD_ALIGN_PARAGRAPH],
        note: str,
        body_font_pt: float = 9.0,
        cell_pad_lr_dxa: int = 70,
    ) -> None:
        self.table_registry.append((num, title))
        add_apa_table(
            self.doc,
            num,
            title,
            headers,
            rows,
            col_widths_cm,
            col_alignments,
            note,
            body_font_pt=body_font_pt,
            cell_pad_lr_dxa=cell_pad_lr_dxa,
        )

        self.md.append(f"**Tabla {num}.** *{title}*")
        self.md.append("")
        self.md.append("| " + " | ".join(headers) + " |")
        align_tokens = []
        for al in col_alignments:
            if al == WD_ALIGN_PARAGRAPH.RIGHT:
                align_tokens.append("---:")
            elif al == WD_ALIGN_PARAGRAPH.CENTER:
                align_tokens.append(":---:")
            else:
                align_tokens.append(":---")
        self.md.append("| " + " | ".join(align_tokens) + " |")
        for r in rows:
            escaped = [str(c).replace("|", "\\|") for c in r]
            self.md.append("| " + " | ".join(escaped) + " |")
        self.md.append("")
        self.md.append(f"*Nota.* {note}")
        self.md.append("")

    def figure(
        self,
        num: int,
        filename: str,
        caption_desc: str,
        source_note: str,
        width_cm: float = 15.4,
    ) -> None:
        img_path = FIGURAS_DIR / filename
        add_figure(
            self.doc,
            num,
            img_path,
            caption_desc,
            source_note,
            width_cm=width_cm,
        )
        self.md.extend(
            [
                f"![Figura {num}](figuras/{filename})",
                "",
                f"**Figura {num}.** *{caption_desc}* {source_note} Elaboración propia.",
                "",
            ]
        )

    def references(self, entries: Sequence[str]) -> None:
        for ref in entries:
            par = self.doc.add_paragraph(style="Normal")
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = par.paragraph_format
            pf.left_indent = Cm(1.27)
            pf.first_line_indent = Cm(-1.27)
            pf.space_before = Pt(0)
            pf.space_after = Pt(2)
            pf.line_spacing = 1.5
            add_inline_runs(par, ref, base_size_pt=12.0)
            self.md.append(f"- {ref}")
        self.md.append("")


# -----------------------------------------------------------------------------
# Contenido integral del informe AE4 SIG
# -----------------------------------------------------------------------------


def build_report(rb: ReportBuilder) -> None:
    """Construye todas las secciones, tablas, figuras, código y referencias."""
    L = WD_ALIGN_PARAGRAPH.LEFT
    C = WD_ALIGN_PARAGRAPH.CENTER
    R = WD_ALIGN_PARAGRAPH.RIGHT

    rb.add_cover()
    rb.add_toc_placeholder()

    # -------------------------------------------------------------------------
    # 1. Introducción
    # -------------------------------------------------------------------------
    rb.h1("1. Introducción")
    rb.p(
        "El crecimiento urbano sostenido de la ciudad de Posadas, capital de la provincia de "
        "Misiones, plantea desafíos concretos para la gestión de la infraestructura vial y la "
        "seguridad del tránsito. Entre las brechas operativas más relevantes se destacan la "
        "ausencia de semaforización en cruces cercanos a establecimientos escolares sobre "
        "avenidas de circulación rápida, la exposición de la calzada ante lluvias intensas en "
        "sectores con drenaje deficiente y la distribución desigual del equipamiento vial entre "
        "el área céntrica y las delegaciones periféricas."
    )
    rb.p(
        "Con el fin de modelar estas problemáticas bajo un enfoque reproducible de Sistemas de "
        "Información Geográfica (Olaya, 2014), este trabajo implementa la Opción A de la "
        "consigna (arquitectura cliente-servidor en PostgreSQL 16.4 y PostGIS 3.4.3 acoplada "
        "con QGIS 4.2.1 y GDAL 3.13.2). El diseño articula dos escalas complementarias: una "
        "regional sobre el Nordeste Argentino (NEA), Misiones y Sudamérica mediante servicios "
        "OGC WFS del Instituto Geográfico Nacional (IGN, s.f.) y Natural Earth 50m (Natural "
        "Earth, s.f.); y una urbana sobre Posadas que integra capas de la Infraestructura de "
        "Datos Espaciales municipal (Municipalidad de Posadas, s.f.), radios censales 2022 "
        "(Instituto Nacional de Estadística y Censos [INDEC], 2023) y la red vial de "
        "OpenStreetMap (OpenStreetMap Contributors, 2026)."
    )
    rb.p(
        "Por rigor metodológico y transparencia científica, la tabla `sig_ae4.incidentes_viales` "
        "(`1.429` eventos) separa explícitamente dos orígenes mediante una restricción `CHECK` "
        "y reporta sus métricas por separado:"
    )
    rb.bullets(
        [
            "**Relevamientos curados de prensa local (`origen = 'real'`):** `12` siniestros "
            "verificados ocurridos en Posadas entre enero y noviembre de 2026 (relevados de "
            "prensa local durante mediados de octubre y noviembre de 2026), sin registro "
            "pluviométrico asociado (`llovia IS NULL`).",
            "**Eventos sintéticos de demostración (`origen = 'simulado'`):** `1.417` incidentes "
            "generados para 2023–2025 en torno a `7` nodos de control vial, con variable booleana "
            "`llovia` (`457` lluvia y `960` seco) y exposición horaria acumulada (`40.348` h-nodo "
            "de lluvia y `143.612` h-nodo secas).",
            "**Nodos de control vial (`nodos_control_vial`):** `7` intersecciones estratégicas "
            "caracterizadas en campo según drenaje pluvial (`ALTO`, `MEDIO`, `BAJO`), carriles y "
            "equipamiento del entorno.",
        ]
    )
    rb.p("Los objetivos específicos del proyecto se resumen en cuatro ejes:")
    rb.bullets(
        [
            "Implementar un esquema espacial normalizado (`sig_ae4`) con estrategia dual de "
            "sistemas de referencia (`EPSG:4326`, `EPSG:5348` y `geography`) y triggers reactivos.",
            "Ingestar, sanear topológicamente (`ogr2ogr` y `ST_MakeValid`) y auditar `18.442` "
            "geometrías sin registros inválidos ni huérfanos.",
            "Resolver las `9` consultas regionales obligatorias (`a–i`), `3` análisis de autoría "
            "urbana y un benchmark de `34` índices GiST hasta `1.000.000` de puntos.",
            "Validar en QGIS 4.2.1 la conexión segura sin credenciales almacenadas, el conteo `1:1` "
            "de las `21` capas, el ciclo transaccional ABM y el bloqueo concurrente MVCC.",
        ]
    )

    # -------------------------------------------------------------------------
    # 2. Fuentes de datos y arquitectura tecnológica
    # -------------------------------------------------------------------------
    rb.h1("2. Fuentes de datos y arquitectura tecnológica")
    rb.p(
        "El entorno cliente-servidor se desplegó mediante contenedores Docker con PostgreSQL "
        "`16.4` (PostgreSQL Global Development Group, 2024) y PostGIS `3.4.3` (`GEOS 3.9.0`, "
        "`PROJ 7.2.1`) (PostGIS Project Steering Committee, 2024), escuchando en el puerto "
        "`5433` para evitar conflictos con instancias locales en `5432`. Esta configuración "
        "garantiza reproducibilidad entre equipos, aislamiento transaccional MVCC real, medición "
        "exacta con `EXPLAIN (ANALYZE, BUFFERS)` y acceso simultáneo desde clientes SQL, scripts "
        "Python, `GDAL 3.13.2` (GDAL/OGR Contributors, 2026) y `QGIS 4.2.1` (QGIS Development "
        "Team, 2026)."
    )
    rb.p(
        "Las capas regionales provienen del GeoServer OGC WFS del IGN (`ign:provincia`, "
        "`ign:departamento`, `ign:localidad_bahra`, hidrografía y red vial), complementadas con "
        "Natural Earth 50m para cubrir los `12` países sudamericanos (dado que `ign:pais` "
        "publica solo el polígono argentino). En Posadas, las capas WFS/SHP de IDE Posadas se "
        "integraron con la red vial de OpenStreetMap y con `459` radios censales del Censo 2022 "
        "(INDEC, 2023), totalizando `331.753` habitantes agregados dentro de las `12` "
        "delegaciones municipales (`Tabla 1`)."
    )

    t1_headers = [
        "Escala",
        "Fuente oficial / origen",
        "Tabla destino",
        "Formato origen",
        "SRID",
        "Registros",
    ]
    t1_rows = [
        ["Regional", "Natural Earth 50m (complemento IGN)", "`paises`", "GeoJSON", "4326", "12"],
        ["Regional", "IGN WFS (`ign:provincia`) + INDEC 2022", "`provincias`", "GeoJSON", "4326", "24"],
        ["Regional", "IGN WFS (`ign:departamento`) + INDEC 2022", "`departamentos`", "GeoJSON", "4326", "529"],
        ["Regional", "IGN-BAHRA WFS (`ign:localidad_bahra`)", "`localidades`", "GeoJSON", "4326", "3.528"],
        ["Regional", "IGN WFS (aguas continentales perennes)", "`cursos_agua`", "GeoJSON", "4326", "1.333"],
        ["Regional", "IGN WFS (`vial_nacional` y `vial_provincial`)", "`rutas`", "GeoJSON", "4326", "582"],
        ["Urbana", "IDE Posadas WFS + 459 radios INDEC 2022", "`delegaciones`", "GeoJSON / SHP", "4326 + 5348", "12"],
        ["Urbana", "IDE Posadas WFS (`Intersecciones_Semaforizadas`)", "`semaforos`", "GeoJSON", "4326 + 5348", "280"],
        ["Urbana", "IDE Posadas WFS (`unidades_funcionales_educativas`)", "`escuelas`", "GeoJSON", "4326 + 5348", "367"],
        ["Urbana", "IDE Posadas WFS (`Refugios_paradas__SIG_0`)", "`paradas`", "GeoJSON", "4326 + 5348", "482"],
        ["Urbana", "IDE Posadas WFS (`manos_unicas`)", "`avenidas_mano_unica`", "GeoJSON", "4326 + 5348", "8"],
        ["Urbana", "IDE Posadas WFS (`asfalto_sobreempedrado0`)", "`asfalto_sobre_empedrado`", "GeoJSON", "4326 + 5348", "613"],
        ["Urbana", "IDE Posadas WFS (`bicisendas_ciclovias0`)", "`ciclovias`", "GeoJSON", "4326 + 5348", "52"],
        ["Urbana", "OpenStreetMap (red vial urbana Posadas)", "`calles`", "JSON nodos", "4326 + 5348", "1.286"],
        ["Urbana", "OpenStreetMap (cruces normalizados)", "`intersecciones`", "JSON puntos", "4326 + 5348", "7.898"],
        ["Urbana", "Relevamiento experto de campo (drenaje)", "`nodos_control_vial`", "Registro Python", "4326 + 5348", "7"],
        ["Urbana", "Prensa local curada + Serie sintética", "`incidentes_viales`", "JSONL", "4326 + 5348", "1.429"],
        ["Alfanum.", "Serie meteorológica horaria (2023–2025)", "`exposicion_clima`", "JSON", "—", "2"],
        ["Auditoría", "Triggers PL/pgSQL (`fn_auditar_edicion`)", "`auditoria_ediciones`", "JSONB", "—", "8"],
    ]
    rb.table(
        1,
        "Inventario de fuentes de datos oficiales y complementarias integradas en el esquema sig_ae4",
        t1_headers,
        t1_rows,
        [1.6, 4.4, 4.45, 1.8, 1.95, 1.7],
        [L, L, L, L, C, R],
        "En `cursos_agua` se consolidan 41 tramos principales (Río Paraná, Río Uruguay y Río Iguazú, "
        "filtrando homónimos patagónicos fuera de la Cuenca del Plata) y 1.292 afluentes en Misiones. "
        "En `rutas` se integran 286 tramos nacionales y 296 tramos provinciales. En `incidentes_viales` "
        "coexisten 12 registros `real` y 1.417 `simulado`. La entidad `nodos_control_vial` se denomina "
        "así en el informe y en la Figura 1 como nombre conceptual académico de la tabla de nodos de "
        "referencia del esquema SQL. `auditoria_ediciones` inicia en 0 tras la carga ETL y alcanza 8 "
        "operaciones tras ejecutar el protocolo transaccional de la Fase III (`05_edicion_transacciones.sql`).",
        body_font_pt=8.8,
        cell_pad_lr_dxa=55,
    )

    # -------------------------------------------------------------------------
    # 3. Fase I: Diseño e implementación de la base de datos espacial
    # -------------------------------------------------------------------------
    rb.h1("3. Fase I: Diseño e implementación de la base de datos espacial")

    rb.h2("3.1 Infraestructura y organización en esquemas")
    rb.p(
        "El servidor separa la ingestión en dos esquemas: `staging`, que recibe geometrías y "
        "atributos crudos sin restricciones restrictivas para aislar defectos de origen, y "
        "`sig_ae4`, esquema productivo normalizado con `19` tablas (`6` regionales, `11` urbanas y "
        "`2` alfanuméricas). Esta arquitectura desacoplada permite auditar codificaciones DBF "
        "heredadas y reparar topologías en SQL antes de validar las reglas productivas."
    )

    rb.h2("3.2 Estrategia de sistemas de referencia")
    rb.p(
        "Operar mediciones euclidianas directamente sobre coordenadas angulares (`EPSG:4326`) "
        "distorsiona distancias y buffers (Olaya, 2014): a latitud de Posadas (`-27,37°`), un "
        "grado de longitud mide cerca de `98,9 km` frente a `110,8 km` en latitud (`~11%` de "
        "anisotropía). Por otro lado, ninguna faja plana única cubre sin deformación todo el "
        "territorio nacional ni el continente sudamericano."
    )
    rb.p(
        "En consecuencia, se adoptó una arquitectura dual para el ámbito urbano y geodésica "
        "esferoidal para el regional (`Tabla 2`). En Posadas (`-55,9°` O) se eligió `EPSG:5348` "
        "(*POSGAR 2007 / Argentina Faja 6*, meridiano central `57°` O), ubicada a solo `1,1°` "
        "de su eje central frente a los `1,9°` respecto de la Faja 7 (`EPSG:5349`), minimizando "
        "el factor de escala lineal. La columna proyectada `geom_m` se recalcula "
        "automáticamente mediante el trigger `trg_01_sync_geom_m` ante cada `INSERT` o `UPDATE` "
        "de `geom`."
    )

    t2_headers = [
        "Sistema / Tipo",
        "Alcance en sig_ae4",
        "Unidades",
        "Justificación técnica y mecanismo de mantenimiento",
    ]
    t2_rows = [
        [
            "`EPSG:4326` (WGS 84 geográfico)",
            "Columna `geom` en las 17 tablas espaciales",
            "Grados decimales",
            "Estándar universal de intercambio WFS/GeoJSON y visualización directa en QGIS; "
            "mantiene compatibilidad nativa con fuentes IGN e IDE Posadas.",
        ],
        [
            "`EPSG:5348` (POSGAR 2007 / Argentina Faja 6)",
            "Columna `geom_m` en las 11 tablas urbanas",
            "Metros planos",
            "Meridiano central 57° O óptimo para Posadas (-55,9° O). Sincronizada "
            "automáticamente `BEFORE INSERT OR UPDATE OF geom` por `trg_01_sync_geom_m`.",
        ],
        [
            "`geography` (WGS 84 esferoidal)",
            "Consultas regionales `a–i` sobre `geom::geography`",
            "Metros sobre elipsoide",
            "Argentina abarca 7 fajas POSGAR (5343–5349) y Sudamérica supera cualquier "
            "proyección plana local. Acelerada mediante índices GiST funcionales.",
        ],
    ]
    rb.table(
        2,
        "Estrategia dual de sistemas de referencia espacial implementada en la base de datos",
        t2_headers,
        t2_rows,
        [3.5, 3.2, 2.3, 6.9],
        [L, L, C, L],
        "Elaboración propia a partir de la definición DDL en `00_init.sql` y el estándar "
        "POSGAR 2007 del Instituto Geográfico Nacional.",
    )

    rb.h2("3.3 Modelo relacional espacial, restricciones e integridad")
    rb.p(
        "De acuerdo con el estándar *Simple Feature Access* (Open Geospatial Consortium [OGC], "
        "2011), todas las tablas espaciales exigen validez geométrica estricta mediante `NOT NULL "
        "CHECK (ST_IsValid(geom))`. Las `19` claves primarias emplean `INTEGER GENERATED ALWAYS "
        "AS IDENTITY` para habilitar la edición concurrente desde QGIS sin colisiones de "
        "secuencias, acompañadas por restricciones de dominio (`origen`, `severidad 1..5`, "
        "`jurisdiccion`, `nivel_drenaje`) y unicidad en códigos oficiales y pares normalizados de "
        "calles (`Figura 1` y `Tabla 3`)."
    )
    rb.p(
        "El comportamiento reactivo se implementa mediante tres funciones PL/pgSQL: "
        "`fn_sync_geom_m()`, disparada como `trg_01_sync_geom_m` en las `11` tablas urbanas; "
        "`fn_sync_incidente_nodos()`, nombrada `trg_02_sync_incidente_nodos` para ejecutarse "
        "alfabéticamente después de `trg_01_sync_geom_m` y enlazar cada incidente con la "
        "intersección OSM más cercana (`<= 150 m`) y el nodo de control más próximo (`<= 500 m`); "
        "y `fn_auditar_edicion()`, que registra cada cambio `INSERT`, `UPDATE` o `DELETE` sobre "
        "`semaforos` e `incidentes_viales` en la bitácora `JSONB` `auditoria_ediciones`."
    )

    rb.figure(
        1,
        "Figura_01_modelo_entidad_relacion.png",
        "Modelo entidad-relación espacial completo del esquema sig_ae4.",
        "Incluye las 19 tablas distribuidas en escala regional, escala urbana y analítica/auditoría, "
        "claves primarias y foráneas, restricciones CHECK, dualidad SRID (4326/5348) y triggers.",
        width_cm=15.4,
    )

    t3_headers = [
        "Bloque del esquema (`sig_ae4`)",
        "Geometría / SRID",
        "Claves y restricciones principales",
        "Triggers y rol funcional",
    ]
    t3_rows = [
        [
            "Escala regional (`6` tablas: límites, localidades, hidrografía, rutas)",
            "`MultiPolygon`, `MultiLineString`, `Point` (`4326`)",
            "PK `IDENTITY`, UQ códigos (`ISO3`, `INDEC`, `BAHRA`, `id_origen`), `3` FKs jerárquicas, CHK `ST_IsValid`, `jurisdiccion`, `poblacion>=0`",
            "Base territorial Sudamérica / Argentina / Misiones para consultas `a–i`",
        ],
        [
            "Infraestructura urbana (`10` tablas: IDE Posadas, OSM y control vial)",
            "`MultiPolygon`, `MultiLineString`, `Point` (`4326` y `5348`)",
            "PK `IDENTITY`, UQ (`id_ide`, `osm_id`, `node_id`, par de calles), CHK `ST_IsValid`, `lanes>0`, `nivel_drenaje`, `subtipo`",
            "`trg_01_sync_geom_m` en las `10` tablas; auditoría DML en `semaforos`",
        ],
        [
            "Siniestralidad urbana (`incidentes_viales`)",
            "`Point` (`4326` y `5348`)",
            "PK `IDENTITY`, UQ `id_origen`, CHK `ST_IsValid`, `origen` (`'real'`/`'simulado'`), `severidad 1..5`, `2` FKs (`interseccion_id`, `nodo_referencia_id`)",
            "`trg_01_sync_geom_m`, `trg_02_sync_incidente_nodos` (`150 m` / `500 m`) y auditoría DML",
        ],
        [
            "Soporte analítico y auditoría (`exposicion_clima`, `auditoria_ediciones`)",
            "Alfanuméricas (columna `GENERATED` y `JSONB`)",
            "PK `IDENTITY`, UQ `condicion` (`lluvia`/`seco`), CHK `operacion` (`INSERT`/`UPDATE`/`DELETE`)",
            "Denominador horario climático (`horas_por_nodo`) y bitácora inmutable de cambios",
        ],
    ]
    rb.table(
        3,
        "Resumen arquitectónico de restricciones, claves y triggers por bloque del esquema sig_ae4",
        t3_headers,
        t3_rows,
        [4.2, 3.3, 4.5, 3.9],
        [L, L, L, L],
        "El inventario detallado tabla por tabla figura en la Tabla 1 y las relaciones completas en "
        "la Figura 1. En `exposicion_clima`, `horas_por_nodo` es una columna generada almacenada "
        "(`horas_nodo_totales / 7`).",
        body_font_pt=8.8,
        cell_pad_lr_dxa=55,
    )

    rb.h2("3.4 Carga, reparación topológica y validación")
    rb.p(
        "El flujo ETL carga primero las capas en `staging` y las sanea declarativamente al "
        "promoverlas a `sig_ae4`. Durante la prueba de ingestión externa con `ogr2ogr` (`GDAL "
        "3.13.2`) leyendo el Shapefile comprimido de delegaciones mediante `/vsizip/` y "
        "`SHAPE_ENCODING=ISO-8859-1` (GDAL/OGR Contributors, 2026), los caracteres acentuados "
        "(`Itaembé Guazú`, `Itaembé Miní Oeste`) ingresaron correctamente, pero `ST_IsValid` "
        "detectó dos autointersecciones puntuales en los polígonos municipales originales."
    )
    rb.p(
        "Esta detección temprana en `staging` justificó aplicar la secuencia "
        "`ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Force2D(geom)), 3))` sobre la capa de "
        "delegaciones antes de poblar producción (`Tabla 4`). De modo complementario, al "
        "reconstruir las `1.286` calles urbanas de OpenStreetMap desde nodos ordenados, se "
        "segmentaron sub-tramos independientes cuando la distancia entre vértices consecutivos "
        "superaba `300 m`, evitando conexiones espurias entre arterias homónimas discontinuas."
    )
    rb.code(
        """-- Normalización y reparación topológica staging -> sig_ae4 (delegaciones)
INSERT INTO sig_ae4.delegaciones
  (id_ide, nombre, poblacion_2022, geom, geom_m)
SELECT dc.id_ide, dc.nombre, COALESCE(SUM(rp.poblacion_n), 0)::INTEGER,
       dc.geom, ST_Transform(dc.geom, 5348)
FROM (
  SELECT REPLACE(TRIM(d.id_ide), 'DELEGACIONES_MUNICIPALES_POSADAS_',
                 'DELEG_POSADAS_') AS id_ide,
         COALESCE(NULLIF(TRIM(d.nombre), ''), TRIM(d.id_ide)) AS nombre,
         ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Force2D(
           ST_SetSRID(ST_GeomFromGeoJSON(d.geom_json), 4326))), 3)) AS geom
  FROM staging.ide_delegaciones d
) dc
LEFT JOIN radios_pts rp ON ST_Within(rp.pt, dc.geom)
GROUP BY dc.id_ide, dc.nombre, dc.geom;"""
    )

    t4_headers = [
        "Control ejecutado (`01_validacion.sql`)",
        "Alcance evaluado",
        "Resultado observado",
        "Estado",
    ]
    t4_rows = [
        ["Validez geométrica (`ST_IsValid`) y no nulidad", "17 tablas espaciales (`18.442` filas)", "`0` geometrías nulas; `0` inválidas", "OK"],
        ["Integridad de SRID (`geom` y `geom_m`)", "17 tablas `4326` + 11 urbanas `5348`", "`0` errores SRID en `4326`; `0` en `5348`", "OK"],
        ["Integridad referencial (5 relaciones FK)", "Jerarquía IGN + vínculos de incidentes", "`0` registros huérfanos", "OK"],
        ["Trigger `trg_02_sync_incidente_nodos` (`real`)", "`12` incidentes reales", "`11` con intersección (`91,7%`); `4` con nodo (`33,3%`)", "OK"],
        ["Trigger `trg_02_sync_incidente_nodos` (`simulado`)", "`1.417` incidentes simulados", "`1.417` con intersección y nodo (`100,0%`)", "OK"],
        ["Total vinculado en `incidentes_viales`", "`1.429` incidentes totales", "`1.428` (`99,9%`) intersec.; `1.421` (`99,4%`) nodo", "OK"],
        ["Sanity check 4A: Capitales nacionales/prov.", "`localidades` BAHRA", "`1` cap. nacional + `23` provinciales = `24`", "OK"],
        ["Sanity check 4B: Vecindad de países NE 50m", "`12` países sudamericanos", "`ST_Touches = ST_Intersects` (`0` solapes)", "OK"],
        ["Sanity check 4C: Vecindad provincial IGN", "`24` provincias argentinas", "Misiones limita solo con Corrientes (`ST_Touches`)", "OK"],
        ["Sanity check 4D: Ríos principales en Misiones", "Paraná (`39`), Uruguay (`1`), Iguazú (`1`)", "`16` intersecciones dpto.-río consistentes", "OK"],
    ]
    rb.table(
        4,
        "Resultados de la auditoría integral de validación geométrica, referencial y topológica",
        t4_headers,
        t4_rows,
        [4.5, 4.0, 5.9, 1.5],
        [L, L, L, C],
        "Resultados de la ejecución verificada de `sql/01_validacion.sql` (disponible en el "
        "Portafolio Digital). Las `18.442` geometrías corresponden a `6.008` entidades regionales "
        "y `12.434` urbanas. El único incidente real sin cruce OSM a `<= 150 m` se ubica sobre "
        "`Av. Alicia Moreau de Justo (Ex Ruta 213)`.",
    )

    # -------------------------------------------------------------------------
    # 4. Fase II: Consultas espaciales y optimización con índices GiST
    # -------------------------------------------------------------------------
    rb.h1("4. Fase II: Consultas espaciales y optimización con índices GiST")

    rb.h2("4.1 Consultas obligatorias — Escala regional (incisos a–i)")
    rb.p(
        "Las nueve consultas regionales obligatorias (`02_consultas_a_i.sql`) emplean el tipo "
        "esferoidal `geography` sobre `EPSG:4326` para calcular áreas, longitudes y distancias "
        "sobre el elipsoide WGS 84 sin distorsión latitudinal, unificando previamente los cursos "
        "fluviales segmentados mediante `ST_Union` para evitar dobles conteos (`Figura 2` y "
        "`Tabla 5`). En accesibilidad troncal e hidrográfica (`g–i`), se observa una cobertura "
        "homogénea: el extremo más alejado del río Paraná dentro de Misiones (`Bernardo de "
        "Irigoyen`, `97,27 km`) queda holgadamente dentro del umbral de `200 km`, mientras "
        "`CROSS JOIN LATERAL` con operador KNN `<->` asigna `67` localidades a la `RN 12`, `66` "
        "a la `RN 14` y `7` a la `RN 101`."
    )
    rb.p(
        "Un hallazgo metodológico clave del inciso `d` surgió al contrastar `ST_Touches` frente "
        "a `ST_Intersects`. Bajo la especificación topológica DE-9IM adoptada por PostGIS "
        "(OGC, 2011; PostGIS Project Steering Committee, 2024), `ST_Touches(A, B)` exige "
        "interiores estrictamente disjuntos (`I(A) ∩ I(B) = ∅`). Mientras los `12` países de "
        "Natural Earth coinciden exactamente entre ambos predicados (`0` solapamientos), la capa "
        "provincial del IGN presenta `4` micro-solapamientos bidimensionales (`0,00` a `5,29 m²` "
        "en `Entre Ríos–Corrientes`, `Buenos Aires–Entre Ríos`, `San Juan–La Rioja` y "
        "`Jujuy–Salta`) que hacen fallar `ST_Touches` pese a ser fronteras vecinas reales."
    )

    rb.figure(
        2,
        "Figura_02_contexto_regional_ign.png",
        "Contexto regional del Nordeste Argentino, hidrografía principal y red vial troncal.",
        "Integración en PostGIS de capas IGN WFS, localidades BAHRA y países Natural Earth 50m "
        "renderizada en QGIS 4.2.1.",
        width_cm=15.4,
    )

    t5_headers = [
        "Inciso",
        "Objetivo analítico",
        "Operadores / funciones PostGIS",
        "Resultados clave verificados",
    ]
    t5_rows = [
        [
            "`a`",
            "Unión relacional localidad → país",
            "`JOIN` jerárquico (4 tablas)",
            "Muestra nacional (`50` filas) + `140` localidades completas de Misiones en `17` departamentos.",
        ],
        [
            "`b`",
            "Jerarquía de capitales",
            "`CASE`, `JOIN`, filtros booleanos",
            "`24` capitales (`1` nacional: Ciudad de Buenos Aires; `23` provinciales, incluida Posadas).",
        ],
        [
            "`c`",
            "Superficie y densidad poblacional",
            "`ST_Area(geom::geography)` / 1e6",
            "`12` países (Brasil `8,47M km²`, Arg. `2,78M km²`) y `17` deptos. Misiones (Capital `407,39 hab/km²`).",
        ],
        [
            "`d`",
            "Adyacencia y fronteras",
            "`ST_Touches` vs `ST_Intersects`",
            "Países `0` discrepancias (`BR=9, AR=5`); provincias `4` micro-solapes IGN (`0,00–5,29 m²`).",
        ],
        [
            "`e`",
            "Overlays ríos vs. jurisdicciones",
            "`ST_Union`, `ST_Intersects`",
            "Paraná y Uruguay cruzan `7` deptos. c/u; Iguazú `2`. Uruguay atraviesa `3` países.",
        ],
        [
            "`f`",
            "Longitud segmentada de ríos",
            "`ST_Length(geography)`, `ST_CollectionExtract`, `ST_Intersection(..., 2)`",
            "En Misiones: Uruguay `336,989 km`, Paraná `246,439 km`, Iguazú `132,217 km` (total `1.845,290 km` Paraná).",
        ],
        [
            "`g`",
            "Alejamiento extremo al Paraná",
            "`ST_Distance(geography)`",
            "`Bernardo de Irigoyen` es la más alejada (`97,266 km`), seguida por `Alicia Baja` (`94,259 km`).",
        ],
        [
            "`h`",
            "Accesibilidad a rutas nacionales",
            "`CROSS JOIN LATERAL` + `<->` + `ST_Distance`",
            "`RN 12`: `67` loc. (`4,415 km` prom.); `RN 14`: `66` (`14,728 km` prom.); `RN 101`: `7` (`5,727 km` prom.).",
        ],
        [
            "`i`",
            "Localidades `< 200 km` del Paraná",
            "`ST_DWithin(geography)` (200 km)",
            "`140` localidades en Misiones (`100%`) y `1.156` en `9` provincias argentinas.",
        ],
    ]
    rb.table(
        5,
        "Síntesis metodológica y resultados verificados de las consultas regionales obligatorias (incisos a–i)",
        t5_headers,
        t5_rows,
        [1.2, 3.1, 4.9, 6.7],
        [C, L, L, L],
        "Resultados obtenidos mediante `sql/02_consultas_a_i.sql` evaluados sobre elipsoide WGS84 "
        "(`geography`). En el inciso `c`, San Pedro contrasta como el departamento más extenso de "
        "Misiones (`3.818,06 km²`, `9,11 hab/km²`) frente a Capital (`964,48 km²`).",
        body_font_pt=9.0,
    )

    rb.h2("4.2 Consultas de autoría — Escala urbana de Posadas")
    rb.p(
        "Las consultas de autoría propias (`03_consultas_autoria.sql`) operan sobre la columna "
        "métrica plana `geom_m` (`EPSG:5348`) y exponen las geometrías `4326` junto con clave `id` "
        "única para integrarse directamente como capas SQL en QGIS, manteniendo separadas las "
        "métricas `real` y `simulado`."
    )

    rb.h3("4.2.1 Incorporación de semaforización en zona escolar (Autoría 1)")
    rb.p(
        "Esta consulta detecta intersecciones OSM ubicadas simultáneamente a `<= 150 m` de una "
        "escuela oficial y a `<= 25 m` de una avenida de mano única, pero sin semáforo dentro de "
        "un radio de exclusión de `30 m` (`NOT EXISTS` con `ST_DWithin`). El cruce arrojó **`104` "
        "intersecciones candidatas** (`56` próximas a escuelas estatales y `48` a privadas)."
    )
    rb.p(
        "Aunque ninguna esquina registró siniestros dentro de `50 m`, al ampliar la evaluación "
        "al corredor (`250 m`) tres cruces destacan por combinar `1` siniestro real y la mayor "
        "concentración simulada (`Tabla 6` y `Figura 3`): **Beethoven y Avenida Centenario**, "
        "**Avenida Centenario y Derqui** y **Avenida Lavalle y Neumann**, en el entorno inmediato "
        "de `C.F.P. Nº 16` y `E.P.E.T. Nº 01 \"UNESCO\"`. Este criterio permite priorizar nuevos "
        "semáforos o sendas peatonales seguras sobre esos dos ejes."
    )
    rb.code(
        """-- Autoría 1: Intersecciones escolares en av. mano única sin semáforo
SELECT i.id, i.nombre, esc.escuela_cercana, esc.dist_escuela_m,
       ave.avenida_mano_unica, stats.siniestros_corredor_250m_real,
       stats.siniestros_corredor_250m_simulado, i.geom
FROM sig_ae4.intersecciones i
JOIN LATERAL (
  SELECT e.nombre AS escuela_cercana,
         ROUND(ST_Distance(i.geom_m, e.geom_m)::numeric, 1) AS dist_escuela_m
  FROM sig_ae4.escuelas e
  WHERE ST_DWithin(i.geom_m, e.geom_m, 150.0)
  ORDER BY i.geom_m <-> e.geom_m LIMIT 1
) esc ON TRUE
JOIN LATERAL (
  SELECT a.nombre AS avenida_mano_unica
  FROM sig_ae4.avenidas_mano_unica a
  WHERE ST_DWithin(i.geom_m, a.geom_m, 25.0)
  ORDER BY i.geom_m <-> a.geom_m LIMIT 1
) ave ON TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM sig_ae4.semaforos s
  WHERE ST_DWithin(i.geom_m, s.geom_m, 30.0)
);"""
    )

    t6_headers = [
        "Intersección candidata (OSM)",
        "Escuela cercana (IDE)",
        "Sector",
        "Dist. (m)",
        "Avenida mano única",
        "250 m (R/S)",
    ]
    t6_rows = [
        ["Beethoven y Avenida Centenario", "C.F.P. Nº 16", "Estatal", "52,9", "AV. CENTENARIO", "1 / 214"],
        ["Avenida Centenario y Derqui", "E.P.E.T. Nº 01: \"UNESCO\"", "Estatal", "136,3", "AV. CENTENARIO", "1 / 214"],
        ["Avenida Lavalle y Neumann", "E.P.E.T. Nº 01: \"UNESCO\"", "Estatal", "21,4", "AV. LAVALLE", "1 / 117"],
        ["Gobernador Bermúdez y Av. Tambor de Tacuarí", "BACH. HUMANISTA \"MONS. J. KEMERER\"", "Privado", "142,8", "AV. TAMBOR DE TACUARÍ", "0 / 9"],
        ["Pasaje Labat y Avenida Lavalle", "GUARDERIA \"CASA DEL NIÑO\" I.P.S. 9001", "Estatal", "17,8", "AV. LAVALLE", "0 / 0"],
        ["Avenida Kolping y Av. Tambor de Tacuarí", "INST. SUPERIOR \"VERBO DIVINO\"", "Privado", "20,4", "AV. TAMBOR DE TACUARÍ", "0 / 0"],
        ["Avenida Santa Catalina y Suecia", "INST. ADVENTISTA ALTA GRACIA", "Privado", "21,3", "AV. SANTA CATALINA", "0 / 0"],
        ["Calle 96 y Avenida Santa Catalina", "INST. POLITECNICO SAN ARNOLDO JANSSEN", "Privado", "22,1", "AV. SANTA CATALINA", "0 / 0"],
        ["Cucchiaroni y Av. Tambor de Tacuarí", "CEMU Nº 01", "Estatal", "22,1", "AV. TAMBOR DE TACUARÍ", "0 / 0"],
        ["Carola Lorenzini y Av. Ramón Martirenez", "INST. CRISTIANO EMANUEL", "Privado", "23,0", "AV. FRANCISCO DE HARO", "0 / 0"],
    ]
    rb.table(
        6,
        "Primeras 10 intersecciones escolares sobre avenidas de mano única sin semáforo (Autoría 1)",
        t6_headers,
        t6_rows,
        [4.2, 4.3, 1.5, 1.5, 2.8, 1.6],
        [L, L, C, R, L, C],
        "Subconjunto ordenado de las 104 candidatas totales (56 estatales y 48 privadas). La "
        "columna `250 m (R/S)` indica siniestros reales (`R`) y simulados (`S`) en un corredor de "
        "250 m. Todas las filas registraron 0 eventos en el radio estricto de 50 m.",
        body_font_pt=8.8,
    )

    rb.figure(
        3,
        "Figura_03_autoria1_escuelas_sin_semaforo.png",
        "Mapa de las 104 intersecciones escolares en avenidas de mano única sin semáforo.",
        "Destaca las tres intersecciones críticas con siniestralidad real en corredor de 250 m "
        "sobre Av. Centenario y Av. Lavalle.",
        width_cm=15.4,
    )

    rb.h3("4.2.2 Mantenimiento preventivo y sensibilidad climática (Autoría 2)")
    rb.p(
        "La segunda línea analiza la vulnerabilidad húmeda de la red en tres consultas "
        "complementarias. La Parte 2A relaciona los incidentes dentro de `500 m` de los `7` nodos "
        "de control experto (`ALTO`, `MEDIO`, `BAJO` drenaje) normalizados por la exposición "
        "horaria del período 2023–2025 (`5.764` h de lluvia y `20.516` h secas por nodo). En los "
        "eventos simulados (`Tabla 7`), la razón de riesgo bajo lluvia asciende a **`1,74×`** en "
        "drenaje `BAJO` y `MEDIO` frente a **`1,59×`** en drenaje `ALTO`; los `4` incidentes "
        "reales cercanos carecen de dato meteorológico (`llovia IS NULL`), por lo que el patrón "
        "climático se acota estrictamente al conjunto demostrativo."
    )

    t7_headers = [
        "Drenaje",
        "Origen",
        "Nodos",
        "Total",
        "Lluvia",
        "Seco",
        "Sin dato",
        "Tasa lluvia /1000h",
        "Tasa seco /1000h",
        "Razón riesgo",
    ]
    t7_rows = [
        ["BAJO", "`real`", "3", "1", "0", "0", "1", "0,000", "0,000", "—"],
        ["MEDIO", "`real`", "2", "2", "0", "0", "2", "0,000", "0,000", "—"],
        ["ALTO", "`real`", "2", "1", "0", "0", "1", "0,000", "0,000", "—"],
        ["BAJO", "`simulado`", "3", "581", "191", "390", "0", "11,046", "6,337", "1,74×"],
        ["MEDIO", "`simulado`", "2", "408", "134", "274", "0", "11,624", "6,678", "1,74×"],
        ["ALTO", "`simulado`", "2", "428", "132", "296", "0", "11,450", "7,214", "1,59×"],
    ]
    rb.table(
        7,
        "Tasas de siniestralidad por condición climática, nivel de drenaje experto y origen (Autoría 2A)",
        t7_headers,
        t7_rows,
        [1.4, 1.6, 1.1, 1.1, 1.1, 1.1, 1.3, 2.5, 2.5, 2.2],
        [C, C, R, R, R, R, R, R, R, C],
        "Exposición acumulada (trienio 2023–2025) por nivel: `17.292,00` h lluvia y `61.548,00` h seco en `BAJO` "
        "(3 nodos); `11.528,00` h lluvia y `41.032,00` h seco en `MEDIO` y `ALTO` (2 nodos c/u). "
        "Los 4 eventos `real` (2026) dentro de 500 m carecen de registro pluviométrico (`Sin dato = 100%`), "
        "por lo que las tasas por 1.000 h-nodo y la razón de riesgo se evalúan exclusivamente sobre la "
        "serie `simulado` (2023–2025). Severidad promedio en simulados: `1,39/1,39` (`BAJO`), `1,46/1,44` (`MEDIO`), `1,41/1,41` (`ALTO`).",
        body_font_pt=9.0,
    )

    rb.p(
        "En forma complementaria, la Parte 2B jerarquiza las `30` calles con mayor índice de "
        "severidad bajo lluvia (`buffer 40 m`), encabezadas por **Avenida San Martín** (puntaje "
        "`57,89`), **Berón de Astrada** (`33,36`), **Avenida Lavalle** (`33,36`), **Carola "
        "Lorenzini** (`31,21`) y **Uruguay** (`30,68`). A su vez, la Parte 2C evalúa las "
        "`1.286` calles completas según cuenten con obras de `asfalto_sobre_empedrado` (`<= 25 m`, "
        "`Tabla 8`): aunque las arterias asfaltadas concentran el tráfico principal, su proporción "
        "relativa bajo lluvia (`1,66×`) resulta menor que en las vías sin repavimentar (`1,82×`), "
        "orientando tanto la limpieza preventiva de sumideros en corredores troncales como la "
        "pavimentación de arterias secundarias."
    )

    t8_headers = [
        "Obra asfalto s/empedrado",
        "Calles",
        "Long. (km)",
        "Reales",
        "Sim. lluvia",
        "Sim. seco",
        "Totales",
        "Sim. lluvia/km",
        "% lluvia sim.",
        "Razón L/S",
    ]
    t8_rows = [
        ["Sí (`<= 25 m`)", "552", "1.019,30", "18", "926", "1.987", "2.931", "0,91", "31,8%", "1,66×"],
        ["No", "734", "527,00", "5", "71", "139", "215", "0,13", "33,8%", "1,82×"],
    ]
    rb.table(
        8,
        "Comparación global de corredores con obra de asfalto sobre empedrado frente al resto de la red (Autoría 2C)",
        t8_headers,
        t8_rows,
        [2.7, 1.1, 1.5, 1.1, 1.4, 1.4, 1.3, 1.9, 1.8, 1.7],
        [L, R, R, R, R, R, R, R, R, C],
        "Las columnas `Reales`, `Sim. lluvia`, `Sim. seco` y `Totales` contabilizan intersecciones "
        "espaciales calle-evento dentro del buffer de 40 m (`18 + 5 = 23` cruces sobre los 12 siniestros "
        "reales únicos y `2.931 + 215 = 3.146` sobre los 1.429 totales), dado que un incidente en una "
        "esquina impacta simultáneamente a más de una arteria concurrente. Por ello, las razones "
        "lluvia/seco (`1,66×` vs `1,82×`) se interpretan de forma relativa entre ambos grupos. "
        "Severidad promedio simulada (lluvia/seco): `1,42/1,41` con obra y `1,35/1,44` sin obra.",
        body_font_pt=8.8,
    )

    rb.h3("4.2.3 Brecha de equipamiento por delegación municipal (Autoría 3)")
    rb.p(
        "La tercera consulta evalúa la equidad territorial entre las `12` delegaciones de Posadas "
        "cruzando semáforos, refugios, escuelas, población 2022 y siniestralidad mediante el "
        "indicador compuesto `indice_brecha_prioridad`:"
    )
    rb.code(
        """indice_brecha_prioridad =
  ((siniestros_real * 3.0 + siniestros_simulado) / area_km2)
  * (1.0 / (1.0 + (semaforos_cada_100_intersecciones / 10.0)))"""
    )
    rb.p(
        "Los resultados (`Tabla 9` y `Figura 4`) evidencian dos asimetrías complementarias. En "
        "cobertura de control vial, **Sede Central** concentra `44,31` semáforos cada `100` "
        "intersecciones mientras las delegaciones periféricas en expansión **Itaembé Guazú** e "
        "**Itaembé Miní Este** carecen por completo de semáforos oficiales pese a sumar `37.566` "
        "habitantes y `22` escuelas. En prioridad compuesta, los picos se registran en **32-33** "
        "(`51,82`), **Riberas del Paraná** (`49,27`) y **Villa Urquiza** (`4` siniestros "
        "reales), sugiriendo una política dual de semaforización periférica y pacificación en "
        "sectores de alta densidad."
    )

    t9_headers = [
        "Delegación",
        "Área km²",
        "Pob. 2022",
        "Inters.",
        "Sem.",
        "Sem/100",
        "Par.",
        "Esc.",
        "Real",
        "Sim.",
        "Brecha",
    ]
    t9_rows = [
        ["Sede Central", "1,93", "14.911", "167", "74", "44,31", "44", "68", "2", "67", "6,96"],
        ["Villa Urquiza", "6,41", "34.203", "630", "30", "4,76", "61", "49", "4", "183", "20,60"],
        ["32-33", "5,54", "26.117", "592", "25", "4,22", "46", "26", "2", "402", "51,82"],
        ["Riberas del Paraná", "6,82", "29.005", "512", "11", "2,15", "38", "22", "1", "405", "49,27"],
        ["Villa Cabello", "7,90", "47.379", "781", "31", "3,97", "71", "52", "1", "0", "0,27"],
        ["Santa Rita", "8,25", "34.784", "755", "18", "2,38", "37", "24", "1", "133", "13,30"],
        ["Itaembé Guazú", "39,06", "16.993", "663", "0", "0,00", "18", "10", "0", "0", "0,00"],
        ["Itaembé Miní Este", "7,42", "20.573", "462", "0", "0,00", "18", "12", "0", "0", "0,00"],
        ["Dolores Sur", "74,94", "29.015", "454", "1", "0,22", "37", "35", "0", "0", "0,00"],
        ["Itaembé Miní Oeste", "94,52", "21.652", "456", "5", "1,10", "27", "14", "0", "0", "0,00"],
        ["Dolores Norte", "5,96", "25.835", "464", "6", "1,29", "21", "18", "0", "0", "0,00"],
        ["Miguel Lanús", "10,69", "31.286", "560", "13", "2,32", "25", "29", "0", "0", "0,00"],
    ]
    rb.table(
        9,
        "Indicadores de equipamiento vial, población y siniestralidad en las 12 delegaciones de Posadas (Autoría 3)",
        t9_headers,
        t9_rows,
        [2.95, 1.30, 1.50, 1.30, 1.00, 1.85, 1.05, 1.00, 1.05, 1.25, 1.65],
        [L, R, R, R, R, R, R, R, R, R, R],
        "Totales contenidos dentro de los polígonos de delegación: `269,44 km²`, `331.753` "
        "habitantes, `6.496` intersecciones, `214` semáforos, `443` paradas, `359` escuelas, `11` "
        "siniestros reales y `1.190` simulados (`1` incidente real sobre Ex Ruta 213 y `227` "
        "simulados en bordes costeros/arteriales yacen fuera del límite oficial de delegación).",
        body_font_pt=9.0,
        cell_pad_lr_dxa=45,
    )

    rb.figure(
        4,
        "Figura_04_autoria3_brecha_delegaciones.png",
        "Coroplético de cobertura semafórica cada 100 intersecciones y siniestros reales por delegación.",
        "Contrasta el centro urbano semaforizado frente al déficit de Itaembé Guazú e Itaembé Miní Este.",
        width_cm=15.4,
    )

    rb.h2("4.3 Optimización mediante índices espaciales GiST")
    rb.p(
        "Los índices **B-tree** tradicionales ordenan claves escalares unidimensionales (`<`, `=`, "
        "`>`), pero no preservan la vecindad en el plano bidimensional. Para resolver predicados "
        "espaciales, PostGIS implementa sobre **GiST** (*Generalized Search Tree*) una "
        "estructura **R-Tree** (Guttman, 1984) que agrupa cada geometría mediante su Rectángulo "
        "Mínimo Envolvente (*MBR*). Toda búsqueda indexada ejecuta un **filtro grueso** mediante "
        "cajas envolventes (`&&` en `ST_Intersects`, `ST_Within` y `ST_DWithin`, o `<->` en "
        "vecinos cercanos KNN) y luego un **refinamiento exacto** con GEOS sobre las tuplas "
        "candidatas. Frente a **SP-GiST** (más orientado a puntos homogéneos) o **BRIN** "
        "(dependiente del orden físico de almacenamiento), GiST soporta geometrías heterogéneas "
        "y ordenamiento KNN nativo."
    )
    rb.p(
        "Se implementaron **`34` índices GiST** (`1.928 kB` acumulados): `22` en las tablas "
        "urbanas (`geom` y `geom_m`) y `12` en las regionales (`geom` más índices funcionales "
        "`USING GIST ((geom::geography))`). Estos últimos evitan una trampa habitual de PostGIS: "
        "castear `geom::geography` en una consulta invalida el índice estándar "
        "`gist_geometry_ops_2d` y fuerza un `Seq Scan` al cambiar el tipo y la familia de "
        "operadores (`gist_geography_ops`)."
    )
    rb.p(
        "Las mediciones sobre `EXPLAIN (ANALYZE, BUFFERS)` (mediana de `5` corridas, `Tabla 10`) "
        "confirman aceleraciones de **`11,87×`** a **`47,80×`** en cruces reales, y un salto de "
        "**`58,88×`** al incorporar el índice funcional `(geom::geography)` (reduciendo de `~4` "
        "minutos a `4,08 s`). Asimismo, la prueba de escalamiento sintético hasta **`1.000.000` "
        "de puntos** (`Tabla 11` y `Figura 5`) demuestra que GiST contiene el crecimiento de "
        "lecturas de buffers (`8.600` frente a `3.008.336` en `Seq Scan`), sosteniendo "
        "aceleraciones de `17,36×` a `28,16×`."
    )

    t10_headers = [
        "Escenario de consulta (`5` corridas, mediana)",
        "Filas",
        "Sin GiST (ms)",
        "Con GiST (ms)",
        "Speedup",
        "Plan observado (Sin → Con)",
    ]
    t10_rows = [
        [
            "1) `intersecciones × calles` (`ST_DWithin 30 m`)",
            "18.194",
            "4.009,167",
            "337,744",
            "**11,87×**",
            "`Seq Scan` → `Index Scan (geom_m)`",
        ],
        [
            "2) `incidentes × delegaciones` (`ST_Within`)",
            "1.201",
            "22,916",
            "1,779",
            "**12,88×**",
            "`Seq Scan` → `Index Scan (geom_m)`",
        ],
        [
            "3) `localidades × cursos_agua` (KNN `<-> LATERAL`)",
            "3.528",
            "5.459,990",
            "114,235",
            "**47,80×**",
            "`Sort + Seq Scan` → `Index Scan (geom)`",
        ],
        [
            "4) Trampa `geom::geography` (`ST_DWithin 200 km`)",
            "176.665",
            "240.178,937",
            "4.078,849",
            "**58,88×**",
            "Solo `geom` (`Seq Scan`) → Funcional `(geom::geography)`",
        ],
    ]
    rb.table(
        10,
        "Benchmark EXPLAIN (ANALYZE, BUFFERS) en consultas espaciales reales y trampa geom::geography",
        t10_headers,
        t10_rows,
        [4.7, 1.35, 2.1, 2.1, 1.65, 4.0],
        [L, R, R, R, C, L],
        "Mediana de 5 corridas en PostgreSQL 16.4 / PostGIS 3.4.3. En el escenario 3, los bloques "
        "leídos descendieron de `1.238.382` a `35.833`; en el escenario 4 (`geom::geography`), la "
        "columna «Sin GiST» evalúa el uso exclusivo del índice estándar en `geom` (`min=239.142,97 "
        "ms`, `max=242.146,74 ms`) frente al índice funcional (`282.565` → `45.853` buffers).",
        body_font_pt=9.0,
    )

    t11_headers = [
        "Volumen sintético",
        "Coincidencias (`<= 50 m`)",
        "Sin GiST (ms)",
        "Con GiST (ms)",
        "Speedup",
        "Buffers Sin GiST (hit)",
        "Buffers Con GiST (hit)",
    ]
    t11_rows = [
        ["10.000 puntos", "57", "17,005", "0,660", "**25,77×**", "87", "463"],
        ["100.000 puntos", "538", "169,070", "6,003", "**28,16×**", "837", "874"],
        ["1.000.000 puntos", "5.188", "1.134,634", "65,363", "**17,36×**", "3.008.336", "8.600"],
    ]
    rb.table(
        11,
        "Escalamiento de rendimiento espacial Sin GiST vs. Con GiST hasta un millón de puntos",
        t11_headers,
        t11_rows,
        [2.6, 2.4, 2.0, 2.0, 1.7, 2.6, 2.6],
        [L, R, R, R, C, R, R],
        "Mediana de 5 ejecuciones evaluando `ST_DWithin(geom_m, calle, 50 m)` contra Avenida "
        "Quaranta en `EPSG:5348` (`Shared Read Blocks = 0`). La tabla temporal se eliminó al "
        "concluir el experimento restaurando los 34 índices GiST (`sql/04_indices_benchmark.sql`).",
    )

    rb.figure(
        5,
        "Figura_05_benchmark_gist_volumen.png",
        "Curva de escalamiento logarítmico Sin GiST vs. Con GiST para 10.000, 100.000 y 1.000.000 de puntos.",
        "Mediana de 5 ejecuciones por escala evaluando `ST_DWithin(geom_m, calle, 50 m)` contra "
        "Avenida Quaranta en `EPSG:5348`.",
        width_cm=15.0,
    )

    # -------------------------------------------------------------------------
    # 5. Fase III: Interoperabilidad cliente-servidor con QGIS 4.2.1
    # -------------------------------------------------------------------------
    rb.h1("5. Fase III: Interoperabilidad cliente-servidor con QGIS 4.2.1")

    rb.h2("5.1 Conexión segura y organización cartográfica")
    rb.p(
        "El proyecto cartográfico nativo `proyecto_ae4.qgz` para QGIS `4.2.1 'Belém do Pará'` "
        "(QGIS Development Team, 2026), configurado en `EPSG:5348`, fue auditado para garantizar "
        "la ausencia total de credenciales en texto plano (`0` tokens `user=` o `password=` en "
        "el XML empaquetado), delegando la autenticación al almacén cifrado *AuthDB*. El árbol "
        "temático organiza las `11` capas PostGIS urbanas, el subgrupo `Consultas de Autoría "
        "(DB Manager / SQL)`, el servicio WMS externo de IDE Posadas y el grupo `Regional (IGN)` "
        "(`Figura 6`)."
    )

    rb.figure(
        6,
        "Figura_06_posadas_infraestructura_siniestros.png",
        "Cartografía urbana integrada de Posadas: infraestructura vial, nodos de control y siniestralidad.",
        "Visualización en `EPSG:5348` diferenciando los 12 siniestros reales (rombos rojos), los "
        "1.417 eventos sintéticos graduados por severidad y los 7 nodos de control con nivel de drenaje.",
        width_cm=15.4,
    )

    rb.h2("5.2 Ejecución de consultas y validación cruzada")
    rb.p(
        "Mediante el proveedor nativo `postgres` de QGIS `4.2.1` se verificaron las `21` capas "
        "del proyecto (`3` capas SQL dinámicas de autoría, `17` tablas PostGIS y `1` servicio "
        "WMS municipal). La auditoría automatizada confirmó la validez geométrica de todas las "
        "capas y una coincidencia `1:1` de `18.588` entidades frente a las consultas directas en "
        "PostgreSQL (`Tabla 12`)."
    )

    t12_headers = [
        "Grupo de capas en QGIS 4.2.1",
        "Origen",
        "Capas válidas",
        "Entidades QGIS",
        "Entidades PostgreSQL",
        "Coincidencia",
    ]
    t12_rows = [
        ["Consultas de Autoría (Autoría 1: 104; 2B: 30; 3: 12)", "SQL (DB Manager)", "3 / 3", "146", "146", "Sí"],
        ["Capas urbanas de Posadas (`11` tablas `sig_ae4`)", "PostGIS", "11 / 11", "12.434", "12.434", "Sí"],
        ["Capas regionales IGN / Natural Earth (`6` tablas)", "PostGIS", "6 / 6", "6.008", "6.008", "Sí"],
        ["IDE Posadas — Delegaciones (servicio externo)", "WMS externo", "1 / 1", "N/A", "N/A", "Sí"],
        ["**Total verificado**", "4 tipos", "**21 / 21**", "**18.588**", "**18.588**", "**100%**"],
    ]
    rb.table(
        12,
        "Resumen de validación cruzada 1:1 de las 21 capas del proyecto QGIS 4.2.1 frente a PostgreSQL/PostGIS",
        t12_headers,
        t12_rows,
        [4.7, 2.6, 1.9, 2.0, 2.3, 2.4],
        [L, L, C, R, R, C],
        "Validación cruzada ejecutada sobre el proveedor nativo `postgres` de QGIS 4.2.1 (`21` "
        "capas verificadas, `0` credenciales almacenadas). El registro individual completo de las "
        "21 capas forma parte del Portafolio Digital.",
        body_font_pt=9.0,
    )

    rb.h2("5.3 Edición bidireccional, integridad y concurrencia MVCC")
    rb.p(
        "El protocolo transaccional (`05_edicion_transacciones.sql`) validó el ciclo ABM "
        "completo sobre `semaforos` (`TEST_QGIS_01`) e `incidentes_viales` (`sim-000001`), "
        "comprobando el recálculo encadenado de `geom_m`, la reasignación automática de "
        "`interseccion_id` y `nodo_referencia_id` tras desplazar un punto `3.512,44 m` y el "
        "registro inmutable de `8` operaciones en `auditoria_ediciones`. Asimismo, el motor "
        "rechazó tres inserciones inválidas controladas (`SQLSTATE 23514` por geometría en moño y "
        "por `origen` fuera de dominio; `SQLSTATE 23503` por clave foránea inexistente) antes de "
        "restaurar los datos de prueba (`Tabla 13`)."
    )
    rb.p(
        "Finalmente, la prueba de concurrencia cliente-servidor ilustró cómo el control "
        "multiversión **MVCC** de PostgreSQL coordina el búfer de edición de QGIS. Mientras el "
        "usuario digitaliza en QGIS, las ediciones residen en memoria local y el bloqueo a "
        "nivel de fila recién se adquiere al confirmar (*Guardar cambios*). En el ensayo sobre "
        "el cruce `Gral. Lavalle y Urquiza` (`semaforos`), una segunda transacción quedó en "
        "espera pasiva solicitando `transactionid ShareLock` (`wait_event = transactionid`) "
        "hasta que la primera ejecutó `ROLLBACK` tras `2,00 s`, preservando íntegra la "
        "consistencia del sistema."
    )

    t13_headers = [
        "Prueba ejecutada",
        "Objeto / Entidad",
        "Comportamiento / SQLSTATE observado",
        "Estado",
    ]
    t13_rows = [
        [
            "Alta (`INSERT`)",
            "`semaforos` `TEST_QGIS_01`",
            "`geom_m` calculado en `EPSG:5348` (`6.609.213,46; 6.973.175,32`); auditoría `INSERT`.",
            "OK",
        ],
        [
            "Modificación (`UPDATE`)",
            "`incidentes_viales` `sim-000001`",
            "Desplazamiento `3.512,44 m`: `interseccion_id 409→5069`, `nodo_referencia_id 3→1`; restaurado.",
            "OK",
        ],
        [
            "Baja (`DELETE`)",
            "`semaforos` `TEST_QGIS_01`",
            "`0` registros remanentes; auditoría `DELETE` (`8` filas acumuladas en bitácora).",
            "OK",
        ],
        [
            "Rechazo 4a (`ST_IsValid`)",
            "Polígono *bowtie* en `delegaciones`",
            "Rechazo `SQLSTATE 23514` (`delegaciones_geom_check`: *Self-intersection*).",
            "OK",
        ],
        [
            "Rechazo 4b (`CHECK` dominio)",
            "`origen = 'otro'` en `incidentes_viales`",
            "Rechazo `SQLSTATE 23514` (`incidentes_viales_origen_check`).",
            "OK",
        ],
        [
            "Rechazo 4c (`FOREIGN KEY`)",
            "`departamento_id = 999999` en `localidades`",
            "Rechazo `SQLSTATE 23503` (`localidades_departamento_id_fkey`).",
            "OK",
        ],
        [
            "Bloqueo concurrente MVCC",
            "`semaforos` (`Gral. Lavalle y Urquiza`)",
            "Sesión B suspendida en `transactionid ShareLock (granted=False)`; desbloqueo en `2,00 s` tras `ROLLBACK`.",
            "OK",
        ],
    ]
    rb.table(
        13,
        "Síntesis de pruebas transaccionales ABM, rechazos de integridad y bloqueo concurrente MVCC",
        t13_headers,
        t13_rows,
        [3.3, 3.8, 7.3, 1.5],
        [L, L, L, C],
        "Síntesis de los protocolos ejecutados con `sql/05_edicion_transacciones.sql` y la prueba "
        "de concurrencia MVCC sobre PostgreSQL 16.4 / PostGIS 3.4.3.",
    )

    # -------------------------------------------------------------------------
    # 6. Conclusiones
    # -------------------------------------------------------------------------
    rb.h1("6. Conclusiones")
    rb.p(
        "La integración de PostgreSQL `16.4` + PostGIS `3.4.3` con QGIS `4.2.1` y GDAL `3.13.2` "
        "permitió consolidar una arquitectura SIG multiescala trazable para diagnosticar la "
        "infraestructura vial de Posadas dentro de su contexto regional. Sobre fuentes oficiales "
        "se identificaron `104` intersecciones escolares en avenidas de mano única sin semáforo, "
        "una marcada brecha de cobertura entre `Sede Central` y las delegaciones periféricas "
        "`Itaembé Guazú` e `Itaembé Miní Este`, y el patrón completo de accesibilidad fluvial y "
        "troncal de las `140` localidades misioneras."
    )
    rb.p(
        "Desde la ingeniería de bases de datos espaciales sobresalen tres aprendizajes: separar "
        "la ingesta en `staging` permitió reparar topologías defectuosas de origen y explicar por "
        "DE-9IM los cuatro micro-solapamientos provinciales del IGN; la estrategia dual `4326` + "
        "`5348` mantenida por triggers concilia interoperabilidad con rigor métrico urbano; y los "
        "índices funcionales GiST `(geom::geography)` resultan decisivos frente al casteo en "
        "consulta (`58,88×` de ganancia), complementando mejoras de `11,87×` a `47,80×` en cruces "
        "locales y búsquedas KNN."
    )
    rb.p(
        "Como límite metodológico explícito, mientras la infraestructura vial, educativa, "
        "semafórica y censal proviene íntegramente de organismos oficiales, `1.417` de los `1.429` "
        "incidentes viales (`99,16%`) corresponden a registros sintéticos en torno a `7` nodos de "
        "control y los `12` siniestros reales carecen de dato pluviométrico. Por ello, los "
        "indicadores de riesgo bajo lluvia validan la arquitectura analítica y quedan listos "
        "para recalcularse con validez causal plena al incorporar series oficiales de tránsito y "
        "meteorología."
    )

    # -------------------------------------------------------------------------
    # 7. Portafolio digital
    # -------------------------------------------------------------------------
    rb.h1("7. Portafolio digital")
    rb.p(
        "Los scripts reproducibles, el proyecto nativo de QGIS 4.2.1, las láminas cartográficas "
        "y las evidencias de validación se encuentran organizados en la carpeta `AE4` del "
        "portafolio digital de la cátedra:",
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
    )
    rb.bullets(
        [
            "**Carpeta `01_Base_de_Datos_SQL`:** Scripts SQL `00_init.sql` a "
            "`05_edicion_transacciones.sql`, diccionario de datos de las `19` tablas y diagrama "
            "entidad-relación espacial (`Figura_01_modelo_entidad_relacion.png`).",
            "**Carpeta `02_Proyecto_QGIS_y_Mapas`:** Proyecto nativo `proyecto_ae4.qgz` para "
            "QGIS 4.2.1 (sin credenciales almacenadas), guía operativa de la Fase III y cuatro "
            "láminas cartográficas PNG (`1800 × 1150 px`).",
            "**Carpeta `03_Evidencias_y_Benchmark`:** Evidencias de validación geométrica, "
            "consultas `a–i` y de autoría, ingesta `ogr2ogr` (`ISO-8859-1`), verificación `21/21` "
            "de QGIS 4.2.1, benchmark GiST con su gráfico y registros de auditoría MVCC.",
            "**Enlace al portafolio en Google Drive:** https://drive.google.com/drive/folders/1mphEwBvYMbGbwa5v0y2jrXreNZjPw9NO",
        ],
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
    )

    # -------------------------------------------------------------------------
    # 8. Índice de figuras
    # -------------------------------------------------------------------------
    rb.h1("8. Índice de figuras")
    rb.bullets(
        [
            "**Figura 1.** Modelo entidad-relación espacial completo del esquema `sig_ae4` "
            "(19 tablas en tres zonas, restricciones y triggers). Archivo: "
            "`Figura_01_modelo_entidad_relacion.png`.",
            "**Figura 2.** Contexto regional del Nordeste Argentino, hidrografía principal y red "
            "vial troncal (IGN + Natural Earth 50m). Archivo: "
            "`Figura_02_contexto_regional_ign.png`.",
            "**Figura 3.** Mapa de las 104 intersecciones escolares sobre avenidas de mano única "
            "sin semáforo (Autoría 1). Archivo: "
            "`Figura_03_autoria1_escuelas_sin_semaforo.png`.",
            "**Figura 4.** Coroplético de cobertura semafórica cada 100 intersecciones y "
            "siniestros reales en las 12 delegaciones de Posadas (Autoría 3). Archivo: "
            "`Figura_04_autoria3_brecha_delegaciones.png`.",
            "**Figura 5.** Curva de escalamiento logarítmico Sin GiST vs. Con GiST para 10.000, "
            "100.000 y 1.000.000 de puntos sintéticos. Archivo: "
            "`Figura_05_benchmark_gist_volumen.png`.",
            "**Figura 6.** Cartografía urbana integrada de Posadas: infraestructura vial, 7 nodos "
            "de control con drenaje y siniestralidad real vs. sintética. Archivo: "
            "`Figura_06_posadas_infraestructura_siniestros.png`.",
        ],
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
    )

    # -------------------------------------------------------------------------
    # 9. Referencias (APA 7, sangría francesa 1,27 cm)
    # -------------------------------------------------------------------------
    rb.h1("9. Referencias")
    refs = [
        "GDAL/OGR Contributors. (2026). *GDAL/OGR geospatial data abstraction software library "
        "(Version 3.13.2)*. Open Source Geospatial Foundation. https://gdal.org/",
        "Guttman, A. (1984). R-trees: A dynamic index structure for spatial searching. "
        "*Proceedings of the 1984 ACM SIGMOD International Conference on Management of Data*, "
        "47–57. https://doi.org/10.1145/602259.602266",
        "Instituto Geográfico Nacional. (s.f.). *Servicios web geográficos (OGC WFS) y Base de "
        "Asentamientos Humanos de la República Argentina (BAHRA)*. Ministerio de Defensa de la "
        "Nación Argentina. "
        "https://www.ign.gob.ar/NuestrasActividades/InformacionGeoespacial/ServiciosOGC",
        "Instituto Nacional de Estadística y Censos. (2023). *Censo Nacional de Población, "
        "Hogares y Viviendas 2022: Resultados definitivos*. Ministerio de Economía de la Nación "
        "Argentina. https://censo.gob.ar/",
        "Municipalidad de Posadas. (s.f.). *Infraestructura de Datos Espaciales de Posadas (IDE "
        "Posadas): Catálogo GeoNode y servicios WFS/WMS*. https://www.ide.posadas.gob.ar/",
        "Natural Earth. (s.f.). *Free vector and raster map data at 1:10m, 1:50m, and 1:110m "
        "scales (Admin 0 – Countries)*. https://www.naturalearthdata.com/",
        "Olaya, V. (2014). *Sistemas de Información Geográfica*. Creative Commons Attribution "
        "3.0. https://volaya.github.io/libro-sig/",
        "Open Geospatial Consortium. (2011). *OpenGIS Implementation Standard for Geographic "
        "information - Simple feature access - Part 1: Common architecture (OGC 06-103r4)*. "
        "https://www.ogc.org/standards/sfa/",
        "OpenStreetMap Contributors. (2026). *OpenStreetMap planet dump — Posadas street "
        "network extract*. https://www.openstreetmap.org/",
        "PostGIS Project Steering Committee. (2024). *PostGIS 3.4.3 manual*. "
        "https://postgis.net/documentation/",
        "PostgreSQL Global Development Group. (2024). *PostgreSQL 16.4 documentation*. "
        "https://www.postgresql.org/docs/16/",
        "QGIS Development Team. (2026). *QGIS Geographic Information System (Version 4.2.1 "
        "'Belém do Pará')*. Open Source Geospatial Foundation. https://qgis.org/",
    ]
    rb.references(refs)

    rb.populate_table_index()


# -----------------------------------------------------------------------------
# Verificación integral de salidas
# -----------------------------------------------------------------------------


def verify_outputs(docx_path: Path, md_path: Path) -> None:
    """Verifica existencia, ausencia total de términos prohibidos y conteos esperados."""
    assert docx_path.exists() and docx_path.stat().st_size > 10_000, "DOCX no generado o vacío"
    assert md_path.exists() and md_path.stat().st_size > 5_000, "MD no generado o vacío"

    # 1. Extraer todo el texto visible desde python-docx (párrafos, tablas, headers, footers)
    loaded = Document(str(docx_path))
    chunks: List[str] = []
    for p in loaded.paragraphs:
        chunks.append(p.text)
    for t in loaded.tables:
        for row in t.rows:
            for cell in row.cells:
                chunks.append(cell.text)
    for sec in loaded.sections:
        for hdr_ftr in (
            sec.header,
            sec.footer,
            sec.first_page_header,
            sec.first_page_footer,
        ):
            for p in hdr_ftr.paragraphs:
                chunks.append(p.text)
            for t in hdr_ftr.tables:
                for row in t.rows:
                    for cell in row.cells:
                        chunks.append(cell.text)

    # 2. Inspeccionar también todo el texto XML dentro de word/*.xml (cualquier etiqueta)
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    xml_texts: List[str] = []
    content_fonts: set[str] = set()
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                raw = zf.read(name)
                root = ET.fromstring(raw)
                xml_texts.extend(t for t in root.itertext() if t)
                if name == "word/document.xml" or name.startswith(("word/header", "word/footer")):
                    for rfonts in root.iter(f"{w_ns}rFonts"):
                        for val in rfonts.attrib.values():
                            content_fonts.add(val)

    assert content_fonts == {"Times New Roman"}, (
        f"FALLO TIPOGRAFÍA: fuentes detectadas en contenido DOCX {sorted(content_fonts)}"
    )

    md_text = md_path.read_text(encoding="utf-8")
    all_docx_text = "\n".join(chunks) + "\n" + "\n".join(xml_texts)
    full_text = all_docx_text + "\n" + md_text

    assert "aitara" not in full_text.lower(), (
        "FALLO EDITORIAL: Se detectó la cadena prohibida en las salidas generadas."
    )
    bad_idx = all_docx_text.find("`")
    assert bad_idx == -1, (
        "FALLO FORMATO: Se detectaron backticks literales en .docx: "
        f"{all_docx_text[max(0, bad_idx - 30):bad_idx + 40]!r}"
    )
    assert len(loaded.tables) == 13, f"Se esperaban 13 tablas, se encontraron {len(loaded.tables)}"


def main() -> None:
    DOCK_DIR.mkdir(parents=True, exist_ok=True)
    doc = configure_document()
    rb = ReportBuilder(doc)
    build_report(rb)

    doc.save(str(DOCX_PATH))
    MD_PATH.write_text("\n".join(rb.md), encoding="utf-8")

    verify_outputs(DOCX_PATH, MD_PATH)
    print(f"[OK] DOCX generado: {DOCX_PATH} ({DOCX_PATH.stat().st_size:,} bytes)")
    print(f"[OK] MD generado  : {MD_PATH} ({MD_PATH.stat().st_size:,} bytes)")
    print("[OK] Verificación editorial (0 ocurrencias prohibidas) y 13 tablas APA 7 superada.")


if __name__ == "__main__":
    main()
