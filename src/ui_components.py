"""
Shared UI pieces for the StructOptima pages: header, status badges, page titles, result guards and table styling.

The design status shown anywhere comes from ``DesignResults.status`` / ``failures`` only
(``ui_tables.design_status_summary``), never from the audit re-check.
"""
import math

import streamlit as st

from src import ui_state
from src.ui_tables import design_status_summary

STATUS_STYLE = {
    "FAIL": ("red", ":material/cancel:"),
    "WARN": ("orange", ":material/warning:"),
    "PASS": ("green", ":material/check_circle:"),
}
# Cell colours for status columns in tables (text, background)
STATUS_CELL = {"FAIL": ("#B42318", "#FEF3F2"), "WARN": ("#B54708", "#FFFAEB"), "PASS": ("#067647", "#ECFDF3"),
               "NOT DESIGNED": ("#B42318", "#FEF3F2")}

_CSS = """
<style>
.block-container {padding-top: 4.6rem; padding-bottom: 2rem; max-width: 1500px;}
h1, h2, h3 {letter-spacing: -0.01em;}
[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums; font-size: 1.75rem;}
.so-hero {border: 1px solid var(--so-border); border-left-width: 6px; border-radius: 0.6rem; padding: 1rem 1.25rem;
          background: var(--so-bg);}
.so-hero .so-status {font-size: 1.6rem; font-weight: 700; color: var(--so-fg); line-height: 1.2;}
.so-hero .so-sub {color: #475467; margin-top: 0.35rem; font-size: 0.95rem;}
.so-hero.fail {--so-border: #FDA29B; --so-bg: #FEF3F2; --so-fg: #B42318; border-left-color: #D92D20;}
.so-hero.warn {--so-border: #FEC84B; --so-bg: #FFFAEB; --so-fg: #B54708; border-left-color: #F79009;}
.so-hero.pass {--so-border: #A6F4C5; --so-bg: #ECFDF3; --so-fg: #067647; border-left-color: #17B26A;}
.so-member {background: #F5F8FF; border: 1px solid #D1E0FF; border-radius: 0.6rem; padding: 0.8rem 1rem;}
.so-member b {color: #1A1A2E;}
@media (max-width: 768px) {.block-container {padding-left: 1rem; padding-right: 1rem;}
  .so-hero .so-status {font-size: 1.25rem;}}
</style>
"""


def inject_css():
    """Small layout additions on top of the theme in .streamlit/config.toml."""
    st.html(_CSS)


def status_badge(status: str, label: str = None):
    color, icon = STATUS_STYLE.get(status, ("gray", ":material/help:"))
    st.badge(label or status, color=color, icon=icon)


def style_status(df, columns=("Status",)):
    """pandas Styler colouring status columns (FAIL red, WARN amber, PASS green)."""
    def cell(v):
        fg, bg = STATUS_CELL.get(str(v), ("#344054", "transparent"))
        return f"color: {fg}; background-color: {bg}; font-weight: 600"
    cols = [c for c in columns if c in df.columns]
    styler = df.style.format(precision=2, na_rep="-")
    return styler.map(cell, subset=cols) if cols else styler


def page_title(title: str, caption: str = ""):
    st.markdown(f"## {title}")
    if caption:
        st.caption(caption)


def render_project_header(on_setup: bool = False):
    """Project bar above every page once a design exists: name, key inputs, design status, freshness."""
    res = st.session_state.get('design_results')
    if res is None:
        return
    s = design_status_summary(res)
    gm = res.gm
    n_cols = len([c for c in gm.columns if c.level == 0])
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f"**{st.session_state.get('project_name', 'Untitled')}**")
        st.badge(f"{st.session_state.get('num_stories')} storeys · {st.session_state.get('conc_grade')} · "
                 f"Fe{st.session_state.get('fy', 415):.0f} · Zone {st.session_state.get('seismic_zone')}", color="gray")
        st.badge(f"{n_cols} columns · {len(st.session_state.get('beams', []))} beams", color="gray")
        if s["status"] == "PASS":
            status_badge("PASS", "PASS for implemented checks")
        else:
            status_badge(s["status"], f"{s['status']} · {s['n_fail']} fail · {s['n_warn']} warn")
        st.badge("NOT VERIFIED · preliminary", color="gray", icon=":material/gpp_maybe:")
        if ui_state.results_state() == "stale":
            st.badge("Inputs changed — results out of date", color="orange", icon=":material/update:")
            if not on_setup:
                st.page_link("pages/setup.py", label="Review and re-run", icon=":material/refresh:")


def require_results():
    """Stop the page with a pointer to Setup when no design has been run."""
    err = st.session_state.pop('run_error', None)
    if err:
        st.error(err)
    if st.session_state.get('design_results') is None:
        with st.container(border=True):
            st.markdown("#### No design yet")
            st.write("Enter the project inputs and run the design on the Setup page. Results, drawings and reports "
                     "appear here afterwards.")
            st.page_link("pages/setup.py", label="Go to Setup", icon=":material/tune:")
        st.stop()
    stale_notice()


def stale_notice():
    if ui_state.results_state() == "stale":
        st.warning("The inputs on the Setup page have changed since this design was run. Everything on this page "
                   "belongs to the previous inputs until you re-run the design.", icon=":material/update:")


def render_member_search():
    """Search box for member lookup by id; shows the matching member's design summary."""
    gm = st.session_state.get('gm')
    if not gm:
        return None
    query = st.text_input("Find a member", key="member_search", placeholder="Column or beam id, e.g. C1_L0 or B_H_3",
                          label_visibility="collapsed")
    if not query or len(query) < 2:
        return None
    q = query.upper().strip()
    for col in gm.columns:
        if q in col.id.upper():
            r = gm.rebar_schedule.get(col.id) if getattr(gm, 'rebar_schedule', None) else None
            ft = next((f for f in st.session_state.get('footings', []) if f.id == f"F-{col.id}"), None)
            st.html(f"""<div class="so-member"><b>{col.id}</b> · column, level {col.level}<br>
                Size {col.width_nb:.0f} x {col.depth_nb:.0f} mm · service load {col.load_kn:.1f} kN<br>
                Bars {r.main_bars_desc if r else '-'} · ties {r.links_desc if r else '-'} ·
                status <b>{r.status if r else 'NOT DESIGNED'}</b><br>
                Footing {f'{ft.length_m:.2f} x {ft.width_m:.2f} m, {ft.thickness_mm:.0f} mm, {ft.status}' if ft else '-'}
                </div>""")
            return col.id
    for bm in st.session_state.get('all_beams', []):
        if q in bm.id.upper():
            span_m = math.hypot(bm.end_point.x - bm.start_point.x, bm.end_point.y - bm.start_point.y)
            r = gm.get_beam_result(bm.id) if hasattr(gm, 'get_beam_result') else None
            st.html(f"""<div class="so-member"><b>{bm.id}</b> · beam<br>
                Size {bm.properties.width_mm:.0f} x {bm.properties.depth_mm:.0f} mm · span {span_m:.2f} m<br>
                Bottom {r.bottom_bars_desc if r else '-'} · top {r.top_bars_desc if r else '-'} ·
                stirrups {r.stirrups_desc if r else '-'} · status <b>{r.status if r else 'NOT DESIGNED'}</b></div>""")
            return bm.id
    st.caption(f"No member matches '{query}'.")
    return None


def render_quick_reference():
    """IS 456 values used most on site, checked against the printed standard on 2026-10-20."""
    st.caption("Checked against the printed IS 456:2000 (with amendments). Covers depend on exposure and fire rating "
               "- the design uses the larger of Tables 16 and 16A.")
    st.markdown("""
| Item | Value | Clause |
|---|---|---|
| Nominal cover by exposure: mild / moderate / severe / very severe / extreme | 20 / 30 / 45 / 50 / 75 mm | Table 16 |
| Cover: columns / footings, at least | 40 / 50 mm | 26.4.2.1, 26.4.2.2 |
| Max stirrup spacing | 0.75 d or 300 mm | 26.5.1.5 |
| Min beam tension steel | 0.85 bd / fy | 26.5.1.1 |
| Column longitudinal steel | 0.8 % to 6 % (StructOptima limits to 4 %) | 26.5.3.1 |
| Tie pitch | least of: least lateral dimension, 16 φ, 300 mm | 26.5.3.2 |
| Development length Fe415 (M20 / M25) | 47 φ / 40 φ | 26.2.1, 26.2.1.1 |
| Lap in flexural tension | Ld, not less than 30 φ | 26.2.5.1 |
| Basic span / d: cantilever / simply supported / continuous | 7 / 20 / 26 | 23.2.1 |
| Min column size in Zones III–V | 300 mm and 20 × largest beam bar | IS 13920 7.1.1 |
| γc / γs | 1.5 / 1.15 | 36.4.2 |
""")
