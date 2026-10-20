"""
Site measurements compared with the design (replaces the former simulated
SHM / digital-twin helpers, gap analysis N15).

Everything here works on data the user supplies (accelerometer records,
strain-gauge readings, survey coordinates) and on the designed model.  Nothing
is generated, assumed or randomised.  Results are arithmetic on those data;
interpreting them (damage, acceptance) is for the engineer.
"""

from __future__ import annotations

import csv
import io
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

ES_MPA = 200000.0   # modulus of elasticity of reinforcing steel, IS 456 Cl 5.6.3 (SP 16 1.4)


# ----------------------------------------------------------------- parsing --
def parse_numeric_csv(data: bytes, min_columns: int = 2) -> List[List[str]]:
    """Rows of a CSV file (header rows whose first numeric column fails are skipped)."""
    text = data.decode("utf-8-sig", errors="replace")
    rows = []
    for row in csv.reader(io.StringIO(text)):
        row = [c.strip() for c in row]
        if len(row) < min_columns or not any(row):
            continue
        rows.append(row)
    return rows


def _floats(rows: List[List[str]], cols: Sequence[int]) -> List[Tuple[float, ...]]:
    out = []
    for r in rows:
        try:
            out.append(tuple(float(r[c]) for c in cols))
        except (ValueError, IndexError):
            continue        # header or malformed line
    return out


# ---------------------------------------------------------------- vibration --
def vibration_spectrum(time_s: Sequence[float], accel: Sequence[float]) -> Dict:
    """Amplitude spectrum of a measured acceleration record (Hann window, mean removed).

    Requires >= 64 samples at (near) uniform spacing.  Returns the frequencies,
    amplitudes, sampling rate, resolution and the dominant non-zero frequency.
    """
    t = np.asarray(time_s, dtype=float)
    a = np.asarray(accel, dtype=float)
    if t.size != a.size or t.size < 64:
        raise ValueError("need at least 64 samples of (time, acceleration)")
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(a))):
        raise ValueError("record contains non-numeric values")
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("time values must increase")
    mean_dt = float(dt.mean())
    if float(np.max(np.abs(dt - mean_dt))) > 0.01 * mean_dt:
        raise ValueError("sampling is not uniform (time steps differ by more than 1 %)")
    fs = 1.0 / mean_dt
    x = (a - a.mean()) * np.hanning(a.size)
    amp = np.abs(np.fft.rfft(x)) * 2.0 / np.sum(np.hanning(a.size))
    freq = np.fft.rfftfreq(a.size, d=mean_dt)
    k = 1 + int(np.argmax(amp[1:])) if amp.size > 1 else 0
    return {"freq_hz": freq.tolist(), "amplitude": amp.tolist(), "sampling_hz": fs,
            "resolution_hz": fs / a.size, "duration_s": float(t[-1] - t[0]), "dominant_hz": float(freq[k])}


def spectrum_from_csv(data: bytes) -> Dict:
    pts = _floats(parse_numeric_csv(data), (0, 1))
    if not pts:
        raise ValueError("no numeric (time, acceleration) rows found")
    t, a = zip(*pts)
    return vibration_spectrum(t, a)


def frequency_change(measured_hz: float, baseline_hz: float) -> Dict:
    """Change of a measured natural frequency against a baseline measurement.

    For an unchanged mass, stiffness is proportional to f^2, so (f/f0)^2 is the
    apparent stiffness ratio.  No damage classification is made.
    """
    if measured_hz <= 0 or baseline_hz <= 0:
        raise ValueError("frequencies must be positive")
    return {"change_pct": (measured_hz - baseline_hz) / baseline_hz * 100.0,
            "apparent_stiffness_ratio": (measured_hz / baseline_hz) ** 2}


# ------------------------------------------------------------------- strain --
def strain_readings(rows: Iterable[Tuple[str, float]], fy_mpa: float, es_mpa: float = ES_MPA) -> List[Dict]:
    """Measured reinforcement strains (microstrain) against the yield strain fy / Es."""
    if fy_mpa <= 0 or es_mpa <= 0:
        raise ValueError("fy and Es must be positive")
    ey = fy_mpa / es_mpa
    out = []
    for gauge, micro in rows:
        e = float(micro) * 1e-6
        out.append({"Gauge / member": gauge, "Strain (µε)": float(micro), "Stress if elastic (MPa)": round(e * es_mpa, 1),
                    "Yield strain (µε)": round(ey * 1e6, 0), "Strain / yield strain": round(abs(e) / ey, 3)})
    return out


def strain_from_csv(data: bytes, fy_mpa: float) -> List[Dict]:
    rows = []
    for r in parse_numeric_csv(data):
        try:
            rows.append((r[0], float(r[1])))
        except (ValueError, IndexError):
            continue
    if not rows:
        raise ValueError("no (gauge, microstrain) rows found")
    return strain_readings(rows, fy_mpa)


# ------------------------------------------------------------------ as-built --
def as_built_deviation(gm, survey: Iterable[Tuple[str, float, float]], tolerance_mm: float) -> Dict:
    """Surveyed column positions (id, x m, y m) against the design grid.

    ``tolerance_mm`` is the project's specified positional tolerance (entered by
    the user, not assumed).  Ids are matched to ground-storey columns.
    """
    if tolerance_mm is None or tolerance_mm <= 0:
        raise ValueError("enter the specified positional tolerance")
    design = {c.id: c for c in gm.columns if c.level == 0}
    rows, unknown = [], []
    for cid, x, y in survey:
        c = design.get(str(cid).strip())
        if c is None:
            unknown.append(str(cid))
            continue
        dx, dy = (float(x) - c.x) * 1000.0, (float(y) - c.y) * 1000.0
        d = math.hypot(dx, dy)
        rows.append({"Column": c.id, "Design x (m)": c.x, "Design y (m)": c.y, "Surveyed x (m)": float(x),
                     "Surveyed y (m)": float(y), "dx (mm)": round(dx, 1), "dy (mm)": round(dy, 1),
                     "Deviation (mm)": round(d, 1), "Status": "EXCEEDS TOLERANCE" if d > tolerance_mm else "Within tolerance"})
    missing = sorted(set(design) - {r["Column"] for r in rows})
    return {"rows": rows, "unknown_ids": unknown, "not_surveyed": missing,
            "exceeding": sum(1 for r in rows if r["Status"] != "Within tolerance")}


def survey_from_csv(gm, data: bytes, tolerance_mm: float) -> Dict:
    pts = []
    for r in parse_numeric_csv(data, 3):
        try:
            pts.append((r[0], float(r[1]), float(r[2])))
        except (ValueError, IndexError):
            continue
    if not pts:
        raise ValueError("no (column id, x, y) rows found")
    return as_built_deviation(gm, pts, tolerance_mm)


# ------------------------------------------------------------- member info --
def member_info(gm, beams, footings, marks, member_id: str) -> Dict[str, str]:
    """Design data of one member from the designed model (columns, beams, footings)."""
    for c in gm.columns:
        if c.id == member_id:
            r = gm.rebar_schedule.get(c.id)
            info = {"Type": "Column", "Mark": marks.columns.get(c.id, ""), "Level": str(c.level),
                    "Position (m)": f"x {c.x:.3f}, y {c.y:.3f}", "Size (mm)": f"{c.width_nb:.0f} x {c.depth_nb:.0f}",
                    "Concrete": f"M{gm.fck:.0f}", "Steel": f"Fe{gm.fy:.0f}"}
            if r:
                info.update({"Main bars": r.main_bars_desc, "Ties": r.links_desc, "Status": r.status,
                             "Interaction ratio": f"{r.interaction_ratio:.3f}", "Governing combination": r.governing_combo})
            return info
    for b in beams:
        if b.id == member_id:
            r = gm.get_beam_result(b.id)
            L = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
            info = {"Type": "Beam", "Mark": marks.beams.get(b.id, ""), "Span (m)": f"{L:.3f}",
                    "Concrete": f"M{gm.fck:.0f}", "Steel": f"Fe{gm.fy:.0f}"}
            if r:
                info.update({"Size (mm)": r.size_label, "Top bars": r.top_bars_desc, "Bottom bars": r.bottom_bars_desc,
                             "Stirrups": r.stirrups_desc, "Status": r.status, "Governing combination": r.governing_combo})
            return info
    for f in footings:
        if f.id == member_id:
            return {"Type": "Footing", "Mark": marks.footings.get(f.id, ""),
                    "Size (mm)": f"{f.length_m * 1000:.0f} x {f.width_m * 1000:.0f} x {f.thickness_mm:.0f}",
                    "Bottom steel": f.rebar_desc, "Status": f.status, "Concrete": f"M{gm.fck:.0f}"}
    return {}


def qr_text(info: Dict[str, str], project: str, member_id: str) -> str:
    """Plain-text QR payload with the member's schedule (readable offline by any QR app)."""
    lines = [f"{project} | {member_id}"] + [f"{k}: {v}" for k, v in info.items()]
    lines.append("PRELIMINARY - verify against the issued drawings")
    return "\n".join(lines)


def qr_png(text: str, scale: int = 5) -> bytes:
    import segno
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()
