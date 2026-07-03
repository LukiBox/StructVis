"""
PDF structural report (ReportLab) - multi-page, automatic.

Sections: title page (with optional 3D thumbnail), design & load case, wingbox
definition, Red/Yellow/Green rating, results summary, per-component stress
table + charts, a plain-language explanation (always present, no AI needed),
and an optional AI review. Footer credits "Made by LukiBox".
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle, HRFlowable, PageBreak)

from . import charts, summary
from .. import materials

AUTHOR = "LukiBox"
GITHUB = "https://github.com/LukiBox"
FLOVIS_URL = "https://github.com/LukiBox/Flovis"

_ACCENT = colors.HexColor("#2563eb")
_DARK = colors.HexColor("#111827")
_MUTED = colors.HexColor("#6b7280")
_GREEN = colors.HexColor("#059669")
_YELLOW = colors.HexColor("#d97706")
_RED = colors.HexColor("#dc2626")
_LEVEL_COLOR = {"green": _GREEN, "yellow": _YELLOW, "red": _RED}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("STitle", parent=ss["Title"], fontSize=26,
                          textColor=_DARK, spaceAfter=2))
    ss.add(ParagraphStyle("SSub", parent=ss["Normal"], fontSize=9,
                          textColor=_MUTED, spaceAfter=10))
    ss.add(ParagraphStyle("SH2", parent=ss["Heading2"], fontSize=12,
                          textColor=_ACCENT, spaceBefore=12, spaceAfter=4))
    ss.add(ParagraphStyle("SBody", parent=ss["Normal"], fontSize=9.5,
                          leading=14, textColor=_DARK))
    ss.add(ParagraphStyle("SBig", parent=ss["Normal"], fontSize=11,
                          textColor=_MUTED))
    return ss


def _img(png: bytes, width=85 * mm):
    img = Image(io.BytesIO(png))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = width * ratio
    return img


def _kv_table(rows, ss):
    data = [[Paragraph(f"<b>{k}</b>", ss["SBody"]), Paragraph(str(v), ss["SBody"])]
            for k, v in rows]
    t = Table(data, colWidths=[68 * mm, 92 * mm])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eef2f7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _rating_table(verdicts, ss):
    rows = [["Metric", "Value", "Rating", "Comment"]]
    styles = [("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, -1), 8.5),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
              ("TOPPADDING", (0, 0), (-1, -1), 4),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for ri, v in enumerate(verdicts, start=1):
        rows.append([v.name, v.value, v.tag, Paragraph(v.comment, ss["SBody"])])
        styles.append(("BACKGROUND", (2, ri), (2, ri), _LEVEL_COLOR[v.level]))
        styles.append(("TEXTCOLOR", (2, ri), (2, ri), colors.white))
        styles.append(("ALIGN", (2, ri), (2, ri), "CENTER"))
    t = Table(rows, colWidths=[38 * mm, 26 * mm, 20 * mm, 76 * mm])
    t.setStyle(TableStyle(styles))
    return t


def _component_table(result, ss):
    comp = result.component_max_vm()
    fos_map = result.component_min_fos()
    rows = [["Component", "Peak Von Mises", "Local FoS"]]
    styles = [("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, -1), 8.5),
              ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
              ("ALIGN", (1, 0), (-1, -1), "CENTER"),
              ("TOPPADDING", (0, 0), (-1, -1), 3),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    friendly = summary._FRIENDLY
    for ri, (name, vm) in enumerate(sorted(comp.items(), key=lambda kv: -kv[1]),
                                    start=1):
        fos = fos_map.get(name, float("inf"))
        rows.append([friendly.get(name, name), f"{vm/1e6:.1f} MPa",
                     f"{fos:.2f}" if fos < 100 else ">100"])
        if fos < 1.0:
            styles.append(("TEXTCOLOR", (2, ri), (2, ri), _RED))
        elif fos < 1.5:
            styles.append(("TEXTCOLOR", (2, ri), (2, ri), _YELLOW))
        else:
            styles.append(("TEXTCOLOR", (2, ri), (2, ri), _GREEN))
    t = Table(rows, colWidths=[70 * mm, 45 * mm, 45 * mm])
    t.setStyle(TableStyle(styles))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(18 * mm, 10 * mm,
                      f"StructVis - structural analysis report  |  Made by {AUTHOR}")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
    canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
    canvas.restoreState()


def build_report(result, output_path, project=None, params=None,
                 load_case=None, design=None, strip_loads=None,
                 total_mass_kg=None, ai_text=None,
                 thumbnail_png=None, buckling=None) -> Path:
    """Build the multi-page structural PDF report."""
    output_path = Path(output_path)
    if output_path.suffix != ".pdf":
        output_path = output_path.with_suffix(".pdf")
    ss = _styles()
    name = project.model.name if project else "Wingbox"
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f"StructVis - {name}", author=AUTHOR)
    story = []
    s = result.summary()

    # ---- title page ----
    story.append(Spacer(1, 26 * mm))
    story.append(Paragraph("StructVis", ss["STitle"]))
    story.append(Paragraph("Wing structural analysis report", ss["SBig"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_ACCENT))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>{name}</b>", ss["SH2"]))
    story.append(Paragraph(
        f"Solver: CalculiX shell FEA &nbsp;|&nbsp; {datetime.now():%Y-%m-%d %H:%M}",
        ss["SSub"]))
    if thumbnail_png:
        story.append(Spacer(1, 6))
        story.append(_img(thumbnail_png, width=150 * mm))
    story.append(PageBreak())

    # ---- design & load case ----
    if project and params and load_case:
        mat = materials.get(params.material)
        story.append(Paragraph("Design & load case", ss["SH2"]))
        rows = [
            ("Source model", name),
            ("Wing half-span", f"{project.geometry.half_span:.3f} m"),
            ("Aircraft mass", f"{project.mass_kg:.2f} kg"),
            ("Load factor (n)", f"{load_case.load_factor:.1f} g"),
            ("Velocity", f"{load_case.velocity:.0f} m/s"),
            ("Target Factor of Safety", f"{load_case.target_fos:.1f}"),
        ]
        if design:
            rows.append(("Design lift coefficient (CL)", f"{design.CL_design:.2f}"))
            rows.append(("Total lift", f"{design.lift_total:.0f} N"))
        story.append(_kv_table(rows, ss))

        story.append(Paragraph("Wingbox definition", ss["SH2"]))
        wrows = [
            ("Front / rear spar", f"{params.front_spar*100:.0f}% / "
                                  f"{params.rear_spar*100:.0f}% chord"),
            ("Ribs", f"{params.n_ribs}"),
            ("Skin gauge", f"{params.skin_t*1000:.2f} mm"),
            ("Spar web / cap", f"{params.web_t*1000:.2f} / {params.cap_t*1000:.2f} mm"),
            ("Rib gauge", f"{params.rib_t*1000:.2f} mm"),
            ("Stringers", f"{params.n_stringers} per skin @ {params.stringer_t*1000:.2f} mm"),
        ]

        def _mat_line(m):
            return (f"{m.name}  (E={m.E/1e9:.0f} GPa, "
                    f"yield={m.yield_strength/1e6:.0f} MPa, "
                    f"density={m.rho:.0f} kg/m3)")

        supp = materials.get(params.effective_support_material)
        if supp.key == mat.key:
            wrows.append(("Material (all)", _mat_line(mat)))
        else:
            wrows.append(("Skin / wing material", _mat_line(mat)))
            wrows.append(("Support material (spars/caps/ribs)", _mat_line(supp)))
        story.append(_kv_table(wrows, ss))

    # ---- rating ----
    if load_case:
        story.append(Paragraph("Rating", ss["SH2"]))
        story.append(_rating_table(summary.verdicts(result, load_case), ss))

    # ---- results summary ----
    story.append(Paragraph("Results summary", ss["SH2"]))
    rrows = [
        ("Max Von Mises stress", f"{s['max_von_mises_MPa']:.1f} MPa "
                                 f"(yield {s['yield_MPa']:.0f} MPa)"),
        ("Critical location", summary._FRIENDLY.get(
            s["critical_component"], s["critical_component"])),
        ("Minimum Factor of Safety", f"{s['min_FoS']:.2f}"),
        ("Tip deflection", f"{s['tip_deflection_mm']:.1f} mm "
                           f"({s['tip_deflection_pct_span']:.1f}% of span)"),
        ("Tip twist", f"{s['tip_twist_deg']:+.2f}°"),
    ]
    if load_case is not None:
        mos = s["min_FoS"] / max(load_case.target_fos, 1e-6) - 1.0
        rrows.append(("Margin of Safety (yield)",
                      f"{mos:+.2f}  (FoS {s['min_FoS']:.2f} / target "
                      f"{load_case.target_fos:.1f} - 1)"))
    if buckling is not None:
        cf = buckling.critical_factor
        verdict = "buckles below limit!" if cf < 1.0 else "safe"
        rrows.append(("Critical buckling factor", f"{cf:.2f}  ({verdict})"))
    if total_mass_kg is not None:
        rrows.append(("Wing structural mass", f"{total_mass_kg*1000:.0f} g"))
    story.append(_kv_table(rrows, ss))

    # ---- charts ----
    imgs = []
    try:
        if strip_loads is not None and project is not None:
            imgs.append(_img(charts.load_distribution_png(
                project.geometry, strip_loads), width=88 * mm))
    except Exception:  # noqa: BLE001
        pass
    try:
        imgs.append(_img(charts.component_stress_png(
            result, result.yield_strength), width=88 * mm))
    except Exception:  # noqa: BLE001
        pass
    if imgs:
        story.append(Spacer(1, 4))
        grid = Table([imgs], colWidths=[92 * mm] * len(imgs))
        grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(grid)

    # ---- component table ----
    story.append(PageBreak())
    story.append(Paragraph("Stress by component", ss["SH2"]))
    story.append(_component_table(result, ss))

    # ---- plain-language explanation (always present) ----
    story.append(Paragraph("Plain-language assessment", ss["SH2"]))
    text = summary.plain_language(result, params, load_case, design,
                                  total_mass_kg) if (params and load_case) else ""
    for para in text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), ss["SBody"]))
            story.append(Spacer(1, 4))

    # ---- optional AI review ----
    story.append(Paragraph("AI review (optional)", ss["SH2"]))
    if ai_text:
        for para in ai_text.split("\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), ss["SBody"]))
                story.append(Spacer(1, 3))
    else:
        story.append(Paragraph(
            "<i>Not used. The assessment above is generated by StructVis "
            "without AI. Run a local Ollama model in the AI Review tab to add "
            "a written second opinion here.</i>", ss["SBody"]))

    # ---- credits ----
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#e5e7eb")))
    story.append(Paragraph(
        f'Made by <b>{AUTHOR}</b> &nbsp;•&nbsp; '
        f'<a href="{GITHUB}">{GITHUB}</a> &nbsp;•&nbsp; '
        f'Companion to <a href="{FLOVIS_URL}">Flovis</a>', ss["SSub"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
