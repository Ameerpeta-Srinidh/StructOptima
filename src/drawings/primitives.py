"""
Backend-independent 2D drawing primitives in **paper millimetres** (origin at
the bottom-left corner of the sheet).

One `Drawing` is rendered to SVG (generated here), DXF (ezdxf) and PDF
(ReportLab) so the three outputs are always identical in content.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

Point = Tuple[float, float]

# Line weights in mm (ISO 128 series)
LINEWEIGHTS = {"thin": 0.18, "medium": 0.35, "thick": 0.50, "heavy": 0.70}
# Dash patterns in paper mm
DASHES = {"cont": None, "dashed": (3.0, 1.5), "dashdot": (6.0, 1.2, 0.6, 1.2), "hidden": (1.5, 1.0)}
COLORS = {"black": (0, 0, 0), "red": (200, 20, 20), "orange": (225, 120, 0), "grey": (130, 130, 130),
          "blue": (20, 70, 160), "lightgrey": (225, 225, 225), "white": (255, 255, 255)}
DXF_COLOR = {"black": 7, "red": 1, "orange": 30, "grey": 8, "blue": 5, "lightgrey": 9, "white": 7}


@dataclass
class Style:
    lw: str = "thin"
    ltype: str = "cont"
    color: str = "black"
    fill: Optional[str] = None
    layer: str = "0"


@dataclass
class Item:
    kind: str                      # "poly" | "circle" | "text"
    pts: List[Point] = field(default_factory=list)
    closed: bool = False
    r: float = 0.0
    text: str = ""
    size: float = 2.5
    halign: str = "left"           # left | center | right
    valign: str = "bottom"         # bottom | middle | top
    rot: float = 0.0               # degrees, counter-clockwise
    bold: bool = False
    style: Style = field(default_factory=Style)


class Drawing:
    def __init__(self, width: float = 420.0, height: float = 297.0):
        self.width = width
        self.height = height
        self.items: List[Item] = []

    # ------------------------------------------------------------ builders
    def line(self, x1, y1, x2, y2, **kw):
        self.items.append(Item("poly", [(x1, y1), (x2, y2)], False, style=Style(**kw)))

    def polyline(self, pts: Sequence[Point], closed: bool = False, **kw):
        self.items.append(Item("poly", list(pts), closed, style=Style(**kw)))

    def rect(self, x, y, w, h, **kw):
        self.polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], closed=True, **kw)

    def circle(self, cx, cy, r, **kw):
        self.items.append(Item("circle", [(cx, cy)], r=r, style=Style(**kw)))

    def text(self, x, y, s, size=2.5, halign="left", valign="bottom", rot=0.0, bold=False, **kw):
        self.items.append(Item("text", [(x, y)], text=str(s), size=size, halign=halign, valign=valign,
                               rot=rot, bold=bold, style=Style(**kw)))

    def layers(self) -> List[str]:
        return sorted({i.style.layer for i in self.items})

    # ---------------------------------------------------------------- SVG
    def to_svg(self) -> str:
        H = self.height
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}mm" height="{H}mm" '
               f'viewBox="0 0 {self.width} {H}" font-family="Helvetica, Arial, sans-serif">',
               f'<rect x="0" y="0" width="{self.width}" height="{H}" fill="white"/>']
        for it in self.items:
            st = it.style
            col = "rgb(%d,%d,%d)" % COLORS.get(st.color, (0, 0, 0))
            if it.kind == "text":
                (x, y) = it.pts[0]
                anchor = {"left": "start", "center": "middle", "right": "end"}[it.halign]
                base = {"bottom": "alphabetic", "middle": "central", "top": "hanging"}[it.valign]
                tr = f' transform="rotate({-it.rot:.3f} {x:.3f} {H - y:.3f})"' if it.rot else ""
                wt = ' font-weight="bold"' if it.bold else ""
                out.append(f'<text x="{x:.3f}" y="{H - y:.3f}" font-size="{it.size:.3f}" fill="{col}" '
                           f'text-anchor="{anchor}" dominant-baseline="{base}"{wt}{tr}>{escape(it.text)}</text>')
                continue
            lw = LINEWEIGHTS.get(st.lw, 0.18)
            dash = DASHES.get(st.ltype)
            da = f' stroke-dasharray="{",".join(str(v) for v in dash)}"' if dash else ""
            fill = "rgb(%d,%d,%d)" % COLORS[st.fill] if st.fill else "none"
            if it.kind == "circle":
                (x, y) = it.pts[0]
                out.append(f'<circle cx="{x:.3f}" cy="{H - y:.3f}" r="{it.r:.3f}" stroke="{col}" '
                           f'stroke-width="{lw}" fill="{fill}"{da}/>')
            else:
                pts = " ".join(f"{x:.3f},{H - y:.3f}" for x, y in it.pts)
                tag = "polygon" if it.closed else "polyline"
                out.append(f'<{tag} points="{pts}" stroke="{col}" stroke-width="{lw}" fill="{fill}" '
                           f'stroke-linejoin="round"{da}/>')
        out.append("</svg>")
        return "\n".join(out)

    # ---------------------------------------------------------------- DXF
    def to_dxf_doc(self):
        """ezdxf document; units = paper millimetres (plot at 1:1)."""
        import ezdxf
        from ezdxf.enums import TextEntityAlignment
        doc = ezdxf.new("R2010", setup=True)
        doc.header["$INSUNITS"] = 4
        doc.header["$LTSCALE"] = 1.0
        msp = doc.modelspace()
        for name in self.layers():
            if name not in doc.layers:
                doc.layers.add(name)
        align = {("bottom", "left"): TextEntityAlignment.BOTTOM_LEFT,
                 ("bottom", "center"): TextEntityAlignment.BOTTOM_CENTER,
                 ("bottom", "right"): TextEntityAlignment.BOTTOM_RIGHT,
                 ("middle", "left"): TextEntityAlignment.MIDDLE_LEFT,
                 ("middle", "center"): TextEntityAlignment.MIDDLE_CENTER,
                 ("middle", "right"): TextEntityAlignment.MIDDLE_RIGHT,
                 ("top", "left"): TextEntityAlignment.TOP_LEFT,
                 ("top", "center"): TextEntityAlignment.TOP_CENTER,
                 ("top", "right"): TextEntityAlignment.TOP_RIGHT}
        ltmap = {"cont": "CONTINUOUS", "dashed": "DASHED", "dashdot": "DASHDOT", "hidden": "HIDDEN"}
        for it in self.items:
            st = it.style
            attrs = {"layer": st.layer, "color": DXF_COLOR.get(st.color, 7)}
            if it.kind == "text":
                t = msp.add_text(it.text, height=it.size, rotation=it.rot, dxfattribs=attrs)
                t.set_placement(it.pts[0], align=align[(it.valign, it.halign)])
                continue
            attrs["lineweight"] = int(round(LINEWEIGHTS.get(st.lw, 0.18) * 100))
            attrs["linetype"] = ltmap.get(st.ltype, "CONTINUOUS")
            if it.kind == "circle":
                msp.add_circle(it.pts[0], it.r, dxfattribs=attrs)
                if st.fill:
                    h = msp.add_hatch(color=DXF_COLOR.get(st.fill, 7), dxfattribs={"layer": st.layer})
                    h.paths.add_edge_path().add_arc(it.pts[0], it.r, 0, 360)
            else:
                msp.add_lwpolyline(it.pts, close=it.closed, dxfattribs=attrs)
                if st.fill and it.closed:
                    h = msp.add_hatch(color=DXF_COLOR.get(st.fill, 7), dxfattribs={"layer": st.layer})
                    h.paths.add_polyline_path(it.pts, is_closed=True)
        return doc

    def to_dxf_bytes(self) -> bytes:
        buf = io.StringIO()
        self.to_dxf_doc().write(buf)
        return buf.getvalue().encode("utf-8")

    # ---------------------------------------------------------- ReportLab
    def draw_reportlab(self, c):
        """Draw onto a ReportLab canvas whose page size equals the sheet."""
        from reportlab.lib.units import mm
        for it in self.items:
            st = it.style
            r, g, b = (v / 255.0 for v in COLORS.get(st.color, (0, 0, 0)))
            if it.kind == "text":
                c.saveState()
                c.setFillColorRGB(r, g, b)
                font = "Helvetica-Bold" if it.bold else "Helvetica"
                c.setFont(font, it.size * mm)   # text height in mm -> points
                x, y = it.pts[0]
                c.translate(x * mm, y * mm)
                if it.rot:
                    c.rotate(it.rot)
                dy = {"bottom": 0.0, "middle": -0.35 * it.size, "top": -0.75 * it.size}[it.valign] * mm
                if it.halign == "center":
                    c.drawCentredString(0, dy, it.text)
                elif it.halign == "right":
                    c.drawRightString(0, dy, it.text)
                else:
                    c.drawString(0, dy, it.text)
                c.restoreState()
                continue
            c.saveState()
            c.setStrokeColorRGB(r, g, b)
            c.setLineWidth(LINEWEIGHTS.get(st.lw, 0.18) * mm)
            dash = DASHES.get(st.ltype)
            if dash:
                c.setDash([v * mm for v in dash])
            fill = 0
            if st.fill:
                fr, fg, fb = (v / 255.0 for v in COLORS[st.fill])
                c.setFillColorRGB(fr, fg, fb)
                fill = 1
            if it.kind == "circle":
                x, y = it.pts[0]
                c.circle(x * mm, y * mm, it.r * mm, stroke=1, fill=fill)
            else:
                p = c.beginPath()
                p.moveTo(it.pts[0][0] * mm, it.pts[0][1] * mm)
                for x, y in it.pts[1:]:
                    p.lineTo(x * mm, y * mm)
                if it.closed:
                    p.close()
                c.drawPath(p, stroke=1, fill=fill if it.closed else 0)
            c.restoreState()
