"""
Headless UI smoke tests with streamlit.testing (no server, no browser).

They run app.py, accept the disclaimer, press "Run Analysis" and then switch
to every page, asserting that no script raises and that the design status is
shown.  Rendering correctness is not checked.
"""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(f for f in os.listdir(os.path.join(ROOT, "pages")) if f.endswith(".py"))


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.chdir(tmp_path)   # pages write DXF exports to the CWD - keep them out of the repo
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=180)
    at.run()
    assert not at.exception
    return at


def _run_analysis(at):
    at.number_input(key="sbc_input").set_value(200.0).run()
    at.checkbox(key="site_params_checkbox").check().run()
    at.checkbox(key="disclaimer_checkbox").check().run()
    run_btn = next(b for b in at.button if b.label == "Run Analysis")
    run_btn.click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_app_runs_design_and_shows_status(app):
    at = _run_analysis(app)
    texts = [m.value for m in list(at.error) + list(at.warning) + list(at.success)]
    assert any("Design status" in t for t in texts)
    assert "design_results" in at.session_state


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_after_analysis(app, page, tmp_path):
    at = _run_analysis(app)
    at.switch_page(f"pages/{page}").run()
    assert not at.exception, [e.message for e in at.exception]
    # pages must not write exports into the working directory (finding N10)
    assert not list(tmp_path.iterdir()), [p.name for p in tmp_path.iterdir()]


def test_analysis_page_failure_screen_uses_design_status(app):
    at = _run_analysis(app)
    page = next(p for p in PAGES if "Analysis" in p)
    at.switch_page(f"pages/{page}").run()
    assert not at.exception
    headers = " ".join(str(m.value) for m in at.markdown)
    assert "Design Failures" in headers


def test_run_needs_sbc_and_site_confirmation(app):
    at = app
    at.checkbox(key="disclaimer_checkbox").check().run()
    run_btn = next(b for b in at.button if b.label == "Run Analysis")
    assert run_btn.disabled                                  # no SBC, site parameters not confirmed
    at.number_input(key="sbc_input").set_value(150.0).run()
    assert next(b for b in at.button if b.label == "Run Analysis").disabled
    at.checkbox(key="site_params_checkbox").check().run()
    assert not next(b for b in at.button if b.label == "Run Analysis").disabled


def test_pass_status_is_never_shown_as_verified(app):
    at = _run_analysis(app)
    texts = " ".join(m.value for m in list(at.error) + list(at.warning) + list(at.success))
    assert "NOT VERIFIED" in texts or "FAIL" in texts or "WARN" in texts
    assert any("Checks NOT performed" in e.label for e in at.expander)


def test_site_tools_show_no_simulated_values(app):
    at = _run_analysis(app)
    page = next(p for p in PAGES if "Site_Tools" in p)
    at.switch_page(f"pages/{page}").run()
    assert not at.exception, [e.message for e in at.exception]
    shown = " ".join(str(getattr(e, "value", "")) for e in list(at.text_area) + list(at.markdown) + list(at.metric))
    for fake in ("92.5", "Damage Index", "Health Score", "Simulate", "placeholder.com", "project-phoenix"):
        assert fake not in shown
    summary = next(t for t in at.text_area if t.label == "Preview").value
    res = at.session_state["design_results"]
    assert f"base shear Vb = {res.seismic_result.base_shear_kn:.1f} kN" in summary
