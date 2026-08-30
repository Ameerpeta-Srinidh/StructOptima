"""
Reusable UI components for StructOptima multi-page app.
Provides styled cards, badges, search, project header, and IS code reference.
"""
import streamlit as st
import math


def get_custom_css():
    """Returns the full custom CSS for mobile-responsive, light-themed professional engineering app."""
    return """
    <style>
    /* ===== GLOBAL ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* ===== PROJECT HEADER BAR ===== */
    .project-header {
        background: #FFFFFF;
        padding: 14px 20px;
        border-radius: 10px;
        margin-bottom: 16px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border: 1px solid #E2E8F0;
        border-left: 4px solid #1565C0;
    }
    .project-header .ph-title {
        color: #1A1A2E;
        font-weight: 700;
        font-size: 1.05em;
        margin-right: auto;
        white-space: nowrap;
    }
    .project-header .ph-chip {
        background: #F0F4F8;
        color: #4A5568;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.82em;
        font-weight: 500;
        border: 1px solid #E2E8F0;
        white-space: nowrap;
    }
    .project-header .ph-status-pass {
        background: #E8F5E9;
        color: #2E7D32;
        border-color: #A5D6A7;
    }
    .project-header .ph-status-warn {
        background: #FFF3E0;
        color: #E65100;
        border-color: #FFCC80;
    }
    
    /* ===== METRIC CARDS ===== */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-top: 3px solid #1565C0;
        border-radius: 10px;
        padding: 16px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(21,101,192,0.12);
    }
    .metric-card .mc-value {
        font-size: 1.6em;
        font-weight: 700;
        color: #1565C0;
        margin: 4px 0;
    }
    .metric-card .mc-label {
        font-size: 0.82em;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card .mc-sub {
        font-size: 0.78em;
        color: #A0AEC0;
        margin-top: 4px;
    }
    .metric-card.mc-green { border-top-color: #2E7D32; }
    .metric-card.mc-green .mc-value { color: #2E7D32; }
    .metric-card.mc-amber { border-top-color: #E65100; }
    .metric-card.mc-amber .mc-value { color: #E65100; }
    .metric-card.mc-red { border-top-color: #C62828; }
    .metric-card.mc-red .mc-value { color: #C62828; }
    
    /* ===== STATUS BADGES ===== */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .badge-pass {
        background: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #A5D6A7;
    }
    .badge-fail {
        background: #FFEBEE;
        color: #C62828;
        border: 1px solid #EF9A9A;
    }
    .badge-warn {
        background: #FFF3E0;
        color: #E65100;
        border: 1px solid #FFCC80;
    }
    
    /* ===== D/C RATIO BAR ===== */
    .dc-bar-container {
        background: #E8EDF2;
        border-radius: 6px;
        height: 20px;
        width: 100%;
        position: relative;
        overflow: hidden;
    }
    .dc-bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 6px;
        font-size: 0.72em;
        font-weight: 600;
        color: #fff;
    }
    .dc-green { background: linear-gradient(90deg, #2E7D32, #43A047); }
    .dc-amber { background: linear-gradient(90deg, #E65100, #FF8F00); }
    .dc-red   { background: linear-gradient(90deg, #C62828, #E53935); }
    
    /* ===== SECTION HEADERS ===== */
    .section-header {
        background: #F0F4F8;
        padding: 10px 16px;
        border-left: 4px solid #1565C0;
        border-radius: 0 8px 8px 0;
        margin: 20px 0 12px 0;
        font-size: 1.15em;
        font-weight: 600;
        color: #1A1A2E;
    }
    
    /* ===== SEARCH BOX ===== */
    .search-result-card {
        background: #EBF5FB;
        border: 1px solid #BBDEFB;
        border-radius: 10px;
        padding: 14px 18px;
        margin: 8px 0;
    }
    .search-result-card .sr-id {
        font-size: 1.1em;
        font-weight: 700;
        color: #1565C0;
    }
    .search-result-card .sr-detail {
        font-size: 0.88em;
        color: #4A5568;
        margin-top: 4px;
    }
    
    /* ===== IS CODE REFERENCE CARD ===== */
    .code-ref-card {
        background: #F8F9FA;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 14px;
        font-size: 0.82em;
        line-height: 1.7;
    }
    .code-ref-card .cr-title {
        font-weight: 700;
        color: #1565C0;
        margin-bottom: 6px;
        font-size: 0.9em;
    }
    .code-ref-card .cr-row {
        display: flex;
        justify-content: space-between;
        color: #4A5568;
        border-bottom: 1px solid #EDF2F7;
        padding: 2px 0;
    }
    .code-ref-card .cr-val {
        font-weight: 600;
        color: #1A1A2E;
    }
    
    /* ===== SIDEBAR REDESIGN ===== */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0;
    }
    
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        font-weight: 600;
        color: #1A1A2E;
        padding: 10px;
    }
    
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
        background: #F1F5F9;
        border-radius: 8px;
    }

    [data-testid="stSidebar"] .stSelectbox > div > div, 
    [data-testid="stSidebar"] .stNumberInput > div > div,
    [data-testid="stSidebar"] .stTextInput > div > div {
        border-radius: 6px;
        border: 1px solid #CBD5E1;
    }
    
    [data-testid="stSidebar"] button[kind="primary"] {
        background: linear-gradient(135deg, #1565C0 0%, #0D47A1 100%) !important;
        color: #FFFFFF !important;
        font-weight: bold !important;
        font-size: 1.1em !important;
        padding: 14px 24px !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(21,101,192,0.3) !important;
        width: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(21,101,192,0.4) !important;
    }
    
    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {
        .project-header {
            flex-direction: column;
            align-items: flex-start;
            padding: 12px 14px;
            gap: 8px;
        }
        .project-header .ph-title {
            font-size: 0.95em;
        }
        .project-header .ph-chip {
            font-size: 0.75em;
            padding: 3px 8px;
        }
        .metric-card {
            padding: 12px 14px;
        }
        .metric-card .mc-value {
            font-size: 1.3em;
        }
        .section-header {
            font-size: 1.0em;
            padding: 8px 12px;
        }
        /* Stack columns on mobile */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        /* Smaller dataframes */
        [data-testid="stDataFrame"] {
            font-size: 0.85em;
        }
    }
    
    /* ===== NAVIGATION LINKS ===== */
    .nav-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .nav-card:hover {
        border-color: #90CAF9;
        box-shadow: 0 4px 16px rgba(21,101,192,0.12);
        transform: translateY(-2px);
    }
    .nav-card .nc-icon {
        font-size: 2em;
        margin-bottom: 6px;
    }
    .nav-card .nc-title {
        font-weight: 600;
        color: #1A1A2E;
        font-size: 0.95em;
    }
    .nav-card .nc-desc {
        font-size: 0.78em;
        color: #718096;
        margin-top: 4px;
    }
    </style>
    """


def inject_css():
    """Inject the custom CSS into the current page."""
    st.markdown(get_custom_css(), unsafe_allow_html=True)


def render_project_header():
    """Shows persistent project summary bar from session state."""
    if not st.session_state.get('analysis_done'):
        return
    
    gm = st.session_state.get('gm')
    bom = st.session_state.get('bom')
    audit_results = st.session_state.get('audit_results', [])
    project_name = st.session_state.get('project_name', 'Untitled')
    conc_grade = st.session_state.get('conc_grade', 'M25')
    num_stories = st.session_state.get('num_stories', 1)
    seismic_zone = st.session_state.get('seismic_zone', 'III')
    
    n_cols = len([c for c in gm.columns if c.level == 0]) if gm else 0
    n_beams = len(st.session_state.get('beams', []))
    concrete = f"{bom.total_concrete_vol_m3:.1f} m³" if bom else "—"
    steel = f"{bom.total_steel_weight_kg:.0f} kg" if bom else "—"
    
    failed = [r for r in audit_results if r.status == "FAIL"]
    if failed:
        status_class = "ph-status-warn"
        status_text = f"⚠️ {len(audit_results)-len(failed)}/{len(audit_results)} pass"
    else:
        status_class = "ph-status-pass"
        status_text = f"✅ {len(audit_results)}/{len(audit_results)} pass"
    
    st.markdown(f"""
    <div class="project-header">
        <span class="ph-title">🏗️ {project_name}</span>
        <span class="ph-chip">{num_stories}F · {conc_grade} · Zone {seismic_zone}</span>
        <span class="ph-chip">{n_cols} Cols · {n_beams} Beams</span>
        <span class="ph-chip">{concrete} Conc · {steel} Steel</span>
        <span class="ph-chip {status_class}">{status_text}</span>
    </div>
    """, unsafe_allow_html=True)


def render_member_search():
    """Search bar for member lookup. Returns details card if found."""
    gm = st.session_state.get('gm')
    if not gm:
        return None
    
    query = st.text_input("🔍 Search member (e.g. C1_L0, B_H_3)", 
                          key=f"member_search_{id(gm)}",
                          placeholder="Type column or beam ID...")
    
    if not query or len(query) < 2:
        return None
    
    query_upper = query.upper().strip()
    
    # Search columns
    for col in gm.columns:
        if query_upper in col.id.upper():
            rebar_info = "—"
            ties_info = "—"
            if hasattr(gm, 'rebar_schedule') and col.id in gm.rebar_schedule:
                res = gm.rebar_schedule[col.id]
                rebar_info = res.main_bars_desc
                ties_info = res.links_desc
            
            footing_info = "—"
            footings = st.session_state.get('footings', [])
            level_0_cols = [c for c in gm.columns if c.level == 0]
            if col.level == 0:
                idx = next((i for i, c in enumerate(level_0_cols) if c.id == col.id), None)
                if idx is not None and idx < len(footings):
                    ft = footings[idx]
                    footing_info = f"{ft.length_m:.2f}×{ft.width_m:.2f}×{ft.thickness_mm/1000:.2f}m"
            
            st.markdown(f"""
            <div class="search-result-card">
                <div class="sr-id">📍 {col.id}</div>
                <div class="sr-detail">
                    <b>Size:</b> {col.label} &nbsp;|&nbsp; 
                    <b>Level:</b> {col.level} &nbsp;|&nbsp;
                    <b>Load:</b> {col.load_kn:.1f} kN<br>
                    <b>Steel:</b> {rebar_info} &nbsp;|&nbsp;
                    <b>Ties:</b> {ties_info}<br>
                    <b>Footing:</b> {footing_info}
                </div>
            </div>
            """, unsafe_allow_html=True)
            return col.id
    
    # Search beams
    all_beams = st.session_state.get('all_beams', [])
    for bm in all_beams:
        if query_upper in bm.id.upper():
            span_m = math.hypot(bm.end_point.x - bm.start_point.x, 
                                bm.end_point.y - bm.start_point.y)
            
            rebar_info = "—"
            if hasattr(gm, 'beam_schedule') and bm.id in gm.beam_schedule:
                res = gm.beam_schedule[bm.id]
                rebar_info = f"Bot: {res.bottom_bars_desc} | Stirrups: {res.stirrups_desc}"
            
            st.markdown(f"""
            <div class="search-result-card">
                <div class="sr-id">📐 {bm.id}</div>
                <div class="sr-detail">
                    <b>Size:</b> {bm.properties.width_mm:.0f}×{bm.properties.depth_mm:.0f}mm &nbsp;|&nbsp;
                    <b>Span:</b> {span_m:.2f}m &nbsp;|&nbsp;
                    <b>Level:</b> {getattr(bm, 'level', 0)}<br>
                    <b>Reinforcement:</b> {rebar_info}
                </div>
            </div>
            """, unsafe_allow_html=True)
            return bm.id
    
    st.caption(f"No member found matching '{query}'")
    return None


def render_status_badge(status):
    """Returns styled HTML badge string."""
    if status in ("PASS", "OK", "✅", True):
        return '<span class="badge badge-pass">PASS</span>'
    elif status in ("FAIL", "❌", False):
        return '<span class="badge badge-fail">FAIL</span>'
    else:
        return '<span class="badge badge-warn">CHECK</span>'


def render_dc_ratio_bar(ratio, show_pct=True):
    """Returns styled HTML progress bar for D/C ratio (0.0 to 1.0+)."""
    pct = min(ratio * 100, 100)
    if ratio <= 0.7:
        css_class = "dc-green"
    elif ratio <= 0.9:
        css_class = "dc-amber"
    else:
        css_class = "dc-red"
    
    label = f"{ratio:.0%}" if show_pct else ""
    return f"""
    <div class="dc-bar-container">
        <div class="dc-bar-fill {css_class}" style="width: {pct:.0f}%;">{label}</div>
    </div>
    """


def render_metric_card(label, value, subtitle="", color="blue", icon=""):
    """Render a glassmorphism metric card."""
    color_class = {
        "blue": "", "green": "mc-green", "amber": "mc-amber", "red": "mc-red"
    }.get(color, "")
    
    sub_html = f'<div class="mc-sub">{subtitle}</div>' if subtitle else ""
    icon_html = f'<span style="margin-right: 5px;">{icon}</span>' if icon else ""
    
    st.markdown(f"""
    <div class="metric-card {color_class}">
        <div class="mc-label">{icon_html}{label}</div>
        <div class="mc-value">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_section_header(title, icon=""):
    """Render a gradient section divider."""
    st.markdown(f'<div class="section-header">{icon} {title}</div>', unsafe_allow_html=True)


def render_no_analysis_warning():
    """Shows 'Run Analysis first' message."""
    st.warning("⚠️ No analysis results found. Go to the **Dashboard** page, configure your project, and click **Run Analysis** first.")
    st.stop()


def render_is_code_reference():
    """Sidebar IS 456/IS 1893 quick reference card."""
    st.sidebar.markdown("""
    <div class="code-ref-card">
        <div class="cr-title">📖 IS 456 Quick Reference</div>
        <div class="cr-row"><span>Min cover (beams)</span><span class="cr-val">25 mm</span></div>
        <div class="cr-row"><span>Min cover (columns)</span><span class="cr-val">40 mm</span></div>
        <div class="cr-row"><span>Min cover (footings)</span><span class="cr-val">50 mm</span></div>
        <div class="cr-row"><span>Max stirrup spacing</span><span class="cr-val">0.75d / 300</span></div>
        <div class="cr-row"><span>Min beam steel</span><span class="cr-val">0.85bd/fy</span></div>
        <div class="cr-row"><span>Max column steel</span><span class="cr-val">4% Ag</span></div>
        <div class="cr-row"><span>Lap (Fe415, tension)</span><span class="cr-val">50φ</span></div>
        <div class="cr-row"><span>Dev length (Fe415)</span><span class="cr-val">47φ</span></div>
        <div class="cr-row"><span>Min column size</span><span class="cr-val">230 mm</span></div>
        <div class="cr-row"><span>L/d (simply supp.)</span><span class="cr-val">≤ 20</span></div>
        <div class="cr-row"><span>L/d (cantilever)</span><span class="cr-val">≤ 7</span></div>
        <div class="cr-row"><span>γc / γs</span><span class="cr-val">1.5 / 1.15</span></div>
    </div>
    """, unsafe_allow_html=True)


def render_page_nav_cards():
    """Render navigation cards to other pages on the dashboard — fully clickable via st.page_link."""
    st.markdown('<div class="section-header">📂 Navigate to</div>', unsafe_allow_html=True)

    cards = [
        ("pages/1_📊_Analysis.py",  "📊", "Analysis",   "Seismic, wind & stability checks"),
        ("pages/2_📋_Schedules.py", "📋", "Schedules",  "Column, beam & slab schedules"),
        ("pages/3_📐_Drawings.py",  "📐", "Drawings",   "3D/2D views & DXF exports"),
        ("pages/4_📄_Reports.py",   "📄", "Reports",    "PDF reports & export package"),
        ("pages/5_🔧_Site_Tools.py","🔧", "Site Tools", "BBS, checklists & calculators"),
    ]

    cols = st.columns(len(cards))
    for i, (page, icon, title, desc) in enumerate(cards):
        with cols[i]:
            # Render the visual card shell
            st.markdown(f'''
            <div class="nav-card" style="cursor:pointer;">
                <div class="nc-icon">{icon}</div>
                <div class="nc-title">{title}</div>
                <div class="nc-desc">{desc}</div>
            </div>
            ''', unsafe_allow_html=True)
            # Actual clickable link directly below the card
            st.page_link(page, label=f"Open {title} →")
