"""Site drawing set (A3 sheets) generated from the designed model.

Public API:
    build_drawing_set(gm, beams, footings, project) -> list[Sheet]
    sheets_to_pdf(sheets) -> bytes
    sheets_to_zip(sheets) -> bytes
    compute_marks(gm, beams, footings) -> Marks
"""

import io
import zipfile
from typing import List

from .marks import Marks, compute_marks
from .sheet import Sheet
from .sheets import build_drawing_set


def sheets_to_pdf(sheets: List[Sheet]) -> bytes:
    """Multi-page A3 PDF (ReportLab, decision D-14)."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(420 * mm, 297 * mm))
    c.setTitle("StructOptima drawing set - PRELIMINARY")
    for sh in sheets:
        sh.drawing.draw_reportlab(c)
        c.showPage()
    c.save()
    return buf.getvalue()


def sheets_to_zip(sheets: List[Sheet]) -> bytes:
    """ZIP with the full PDF set plus one DXF and one SVG per sheet."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("StructOptima_Drawings.pdf", sheets_to_pdf(sheets))
        for sh in sheets:
            z.writestr(f"dxf/{sh.number}.dxf", sh.drawing.to_dxf_bytes())
            z.writestr(f"svg/{sh.number}.svg", sh.drawing.to_svg())
    return buf.getvalue()


__all__ = ["build_drawing_set", "sheets_to_pdf", "sheets_to_zip", "compute_marks", "Marks", "Sheet"]
