"""
The Setup page with awkward or broken drawings, run through the real app (streamlit AppTest): a drawing the tool
cannot design is an input message (never an exception, never stored results); a valid but unusual drawing designs.
"""
import pytest

from tests.dxf_corpus import CASES, make, make_hard
from tests.test_streamlit_app import _fill_required, _run_button, _texts, app  # noqa: F401 - fixture


def _bytes(tmp_path, kind):
    if kind == "not-dxf":
        return b"%PDF-1.7\n" + b"0" * 400
    if kind == "empty":
        return b""
    if kind in CASES:
        return open(make(tmp_path / f"{kind}.dxf", dict(CASES[kind])), "rb").read()
    return open(make_hard(tmp_path / f"{kind}.dxf", kind), "rb").read()


@pytest.mark.parametrize("kind, outcome", [
    ("not-dxf", "input"), ("empty", "input"), ("three-columns-L", "input"), ("nan-coordinate", "input"),
    ("rotate-30-skewed", "design"), ("units-in", "design"), ("lines-as-columns", "design"),
])
def test_setup_page_with_awkward_drawings(app, tmp_path, kind, outcome):  # noqa: F811
    at = app
    at.session_state["model_file"] = {"name": f"{kind}.dxf", "bytes": _bytes(tmp_path, kind), "kind": "dxf"}
    at.radio(key="in_mode").set_value("CAD drawing (DXF)").run()
    assert not at.exception, [e.message for e in at.exception]
    _fill_required(at)
    button = _run_button(at)
    if not button.disabled:
        button.click().run()
    assert not at.exception, [e.message for e in at.exception]
    if outcome == "input":
        assert "design_results" not in at.session_state
        assert at.error, "no message shown for a drawing that cannot be designed"
        assert not any("Design failed" in str(e.value) for e in at.error), [str(e.value) for e in at.error]
    else:
        assert "design_results" in at.session_state, _texts(at)
