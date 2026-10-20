"""StructOptima Streamlit entry point: page navigation, shared state and the project header.

The pages live in ``pages/`` and are registered here with ``st.navigation`` (top bar). Project inputs
are kept in session state by ``src.ui_state`` so they survive page switches.
"""
import os
import sys

import streamlit as st

# Ensure src path is visible
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Initialize logging and monitoring BEFORE other imports
from src.logging_config import setup_streamlit_logging, get_logger
from src.monitoring import init_sentry_for_streamlit

setup_streamlit_logging()
logger = get_logger(__name__)
init_sentry_for_streamlit()

from src import ui_state
from src.ui_components import inject_css, render_project_header

st.set_page_config(page_title="StructOptima", layout="wide", page_icon=":material/foundation:")
ui_state.init_inputs()
ui_state.keep_inputs()
inject_css()

PAGES = {
    "setup": st.Page("pages/setup.py", title="Setup", icon=":material/tune:", default=True),
    "overview": st.Page("pages/overview.py", title="Overview", icon=":material/space_dashboard:"),
    "checks": st.Page("pages/checks.py", title="Checks", icon=":material/fact_check:"),
    "members": st.Page("pages/members.py", title="Members", icon=":material/view_column:"),
    "drawings": st.Page("pages/drawings.py", title="Drawings & 3D", icon=":material/architecture:"),
    "reports": st.Page("pages/reports.py", title="Reports", icon=":material/description:"),
    "site": st.Page("pages/site_tools.py", title="Site tools", icon=":material/construction:"),
}

nav = st.navigation(list(PAGES.values()), position="top")

ui_state.ensure_design()
render_project_header(on_setup=nav.url_path == PAGES["setup"].url_path)
nav.run()

st.caption("StructOptima v1.2 · preliminary design aid referencing IS 456:2000 · IS 1893 (Part 1):2016 · IS 875 — "
           "not a substitute for review by a licensed structural engineer")
