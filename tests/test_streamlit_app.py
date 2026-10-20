"""
Headless UI smoke tests with streamlit.testing (no server, no browser).

They run app.py (the navigation entry point), fill the required inputs on the Setup page, run the design
and then switch to every page, asserting that no script raises and that the design status is shown.
Rendering correctness is not checked (screenshots: docs/development/ui-guide.md).
"""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(f for f in os.listdir(os.path.join(ROOT, "pages")) if f.endswith(".py"))
RESULT_PAGES = [p for p in PAGES if p != "setup.py"]


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.chdir(tmp_path)   # pages must not write exports to the CWD - keep them out of the repo
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=180)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _run_button(at):
    return next(b for b in at.button if b.label in ("Run design", "Re-run design"))


def _fill_required(at):
    at.number_input(key="in_sbc").set_value(200.0).run()
    at.checkbox(key="in_site_confirmed").check().run()
    at.checkbox(key="in_disclaimer").check().run()
    return at


def _run_analysis(at):
    _fill_required(at)
    _run_button(at).click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert "design_results" in at.session_state
    return at


def _texts(at):
    return [m.value for m in list(at.error) + list(at.warning) + list(at.success) + list(at.info)]


def test_app_runs_design_and_shows_status(app):
    at = _run_analysis(app)
    assert any("Design status" in t for t in _texts(at))     # the run switches to the Overview page


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_after_analysis(app, page, tmp_path):
    at = _run_analysis(app)
    at.switch_page(f"pages/{page}").run()
    assert not at.exception, [e.message for e in at.exception]
    # pages must not write exports into the working directory (finding N10)
    assert not list(tmp_path.iterdir()), [p.name for p in tmp_path.iterdir()]


@pytest.mark.parametrize("page", [p for p in RESULT_PAGES if p != "site_tools.py"])
def test_result_pages_point_to_setup_without_a_design(app, page):
    app.switch_page(f"pages/{page}").run()
    assert not app.exception, [e.message for e in app.exception]
    assert any("No design yet" in str(m.value) for m in app.markdown)


def test_checks_page_failure_screen_uses_design_status(app):
    at = _run_analysis(app)
    at.switch_page("pages/checks.py").run()
    assert not at.exception
    headers = " ".join(str(m.value) for m in at.markdown)
    assert "Design Failures" in headers


def test_run_needs_sbc_and_site_confirmation(app):
    at = app
    at.checkbox(key="in_disclaimer").check().run()
    assert _run_button(at).disabled                          # no SBC, site parameters not confirmed
    at.number_input(key="in_sbc").set_value(150.0).run()
    assert _run_button(at).disabled
    at.checkbox(key="in_site_confirmed").check().run()
    assert not _run_button(at).disabled


def test_changing_a_site_parameter_clears_the_confirmation(app):
    at = _fill_required(app)
    assert at.session_state["in_site_confirmed"]
    at.selectbox(key="in_zone").set_value("IV").run()
    assert not at.session_state["in_site_confirmed"]
    assert _run_button(at).disabled


def test_inputs_survive_page_switches(app):
    at = app
    at.text_input(key="in_project_name").set_value("Tower A").run()
    at.number_input(key="in_sbc").set_value(180.0).run()
    at.switch_page("pages/site_tools.py").run()
    at.switch_page("pages/setup.py").run()
    assert at.text_input(key="in_project_name").value == "Tower A"
    assert at.number_input(key="in_sbc").value == 180.0


def test_changed_inputs_mark_results_out_of_date(app):
    at = _run_analysis(app)
    at.switch_page("pages/setup.py").run()
    at.number_input(key="in_stories").set_value(3).run()
    at.switch_page("pages/overview.py").run()
    assert any("have changed since this design was run" in t for t in _texts(at))
    at.switch_page("pages/setup.py").run()
    at.number_input(key="in_stories").set_value(2).run()      # back to the inputs of the run
    at.switch_page("pages/overview.py").run()
    assert not any("have changed since this design was run" in t for t in _texts(at))


def test_pass_status_is_never_shown_as_verified(app):
    at = _run_analysis(app)
    texts = " ".join(_texts(at))
    assert "NOT VERIFIED" in texts or "FAIL" in texts or "WARN" in texts
    assert any("Checks NOT performed" in e.label for e in at.expander)


def test_site_tools_show_no_simulated_values(app):
    at = _run_analysis(app)
    at.switch_page("pages/site_tools.py").run()
    assert not at.exception, [e.message for e in at.exception]
    shown = " ".join(str(getattr(e, "value", "")) for e in list(at.text_area) + list(at.markdown) + list(at.metric))
    for fake in ("92.5", "Damage Index", "Health Score", "Simulate", "placeholder.com", "project-phoenix"):
        assert fake not in shown
    summary = next(t for t in at.text_area if t.label == "Preview").value
    res = at.session_state["design_results"]
    assert f"base shear Vb = {res.seismic_result.base_shear_kn:.1f} kN" in summary


def test_bbs_total_states_its_scope(app):
    at = _run_analysis(app)
    at.switch_page("pages/site_tools.py").run()
    captions = " ".join(str(c.value) for c in at.caption)
    assert "one typical floor" in captions
