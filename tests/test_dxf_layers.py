"""
Reading what each DXF layer means when engineers name layers their own way (src/dxf_layers.py).

Every office names layers differently, so the meaning of a layer is suggested from its name AND from what is drawn
on it (closed column-sized outlines, lines that run between columns, parallel line pairs a wall thickness apart).
The engineer confirms or corrects the suggestion on the Setup page; a confirmed mapping is used as given.
"""
import logging
from pathlib import Path

import pytest

from src.cad_loader import CADLoader
from src.cad_parser import CADParser
from src.dxf_layers import analyse_layers
from tests.dxf_conventions import N_BEAMS, N_COLUMNS, make_plan

logging.disable(logging.CRITICAL)
SAMPLES = Path(__file__).resolve().parent.parent / "samples"
ALL_ON_ZERO = {k: "0" for k in ("col", "beam", "wall", "grid", "grid_iden", "col_iden", "dims", "door", "hatch")}


def _roles(path):
    return {i.name: i.role for i in analyse_layers(CADParser(str(path)))}


def _load(path, roles=None):
    loader = CADLoader(str(path), layer_roles=roles)
    gm, beams = loader.load_grid_manager()
    return loader, gm, beams


@pytest.mark.parametrize("layers", ["ncs", "ncs_long", "indian"])
def test_standard_conventions_are_recognised_by_name(tmp_path, layers):
    roles = _roles(make_plan(tmp_path / "p.dxf", layers=layers))
    from tests.dxf_conventions import LAYERS
    L = LAYERS[layers]
    assert roles[L["col"]] == "column" and roles[L["beam"]] == "beam" and roles[L["wall"]] == "wall"
    for k in ("grid", "grid_iden", "col_iden", "dims", "door"):
        assert roles[L[k]] == "ignore", (k, L[k])


@pytest.mark.parametrize("names", [
    {"col": "Layer 7", "beam": "Layer 8", "wall": "Layer 2"},           # default names left by the CAD program
    {"col": "STAMBH", "beam": "PATTI", "wall": "DIWAR"},                 # names in another language
    {"col": "RCC-OUTLINE", "beam": "STR-LINES", "wall": "ARCH-LINES"},  # names that do not say what they hold
])
def test_layers_are_understood_from_what_is_drawn(tmp_path, names):
    path = make_plan(tmp_path / "p.dxf", layer_names=names)
    roles = _roles(path)
    assert roles[names["col"]] == "column"
    assert roles[names["beam"]] == "beam"
    assert roles[names["wall"]] == "wall"
    _, gm, beams = _load(path)
    assert len([c for c in gm.columns if c.level == 0]) == N_COLUMNS and len(beams) == N_BEAMS


def test_everything_on_layer_zero_is_sorted_by_shape(tmp_path):
    path = make_plan(tmp_path / "p.dxf", layer_names=ALL_ON_ZERO)
    info = {i.name: i for i in analyse_layers(CADParser(str(path)))}
    assert info["0"].role == "mixed"
    _, gm, beams = _load(path)
    cols = [c for c in gm.columns if c.level == 0]
    assert len(cols) == N_COLUMNS
    assert {(round(c.width_nb), round(c.depth_nb)) for c in cols} == {(300, 450)}
    assert len(beams) == N_BEAMS                    # grid lines, wall faces and leaders are not beams
    assert gm.walls                                 # parallel pairs read as walls


@pytest.mark.parametrize("name", ["PLINTH BEAM", "LINTEL", "LINTEL BEAM", "PB"])
def test_plinth_and_lintel_beams_are_not_floor_beams(tmp_path, name):
    path = make_plan(tmp_path / "p.dxf", layer_names={"beam": name})
    info = {i.name: i for i in analyse_layers(CADParser(str(path)))}
    assert info[name].role == "ignore" and ("plinth" in info[name].reason.lower() or "lintel" in info[name].reason.lower())


def test_confirmed_mapping_is_used_as_given(tmp_path):
    path = make_plan(tmp_path / "p.dxf")                                  # ncs names
    _, gm, beams = _load(path, roles={"S-COLS": "column", "S-BEAM": "ignore", "A-WALL": "ignore"})
    assert len([c for c in gm.columns if c.level == 0]) == N_COLUMNS
    assert beams == [] and gm.walls == []
    # a layer the engineer marks as walls is read as walls even though its name says grid
    _, gm, _ = _load(path, roles={"S-COLS": "column", "S-GRID": "wall"})
    assert gm.walls


def test_layer_summary_reports_sizes_and_reasons():
    info = {i.name: i for i in analyse_layers(CADParser(str(SAMPLES / "plans" / "complex_house.dxf")))}
    col = info["COLUMNS"]
    assert col.role == "column" and col.n_column_outlines == 11
    assert col.typical_outline_mm == (230, 230)
    assert info["TEXT"].role == "ignore" and info["TEXT"].n_texts == 18
    assert all(i.reason for i in info.values())


def test_room_label_outside_the_structure_is_reported():
    loader, _, _ = _load(SAMPLES / "plans" / "complex_house.dxf")
    msgs = " ".join(loader.load_warnings)
    assert "Master Bed" in msgs and "Main Entry" not in msgs


def test_no_room_label_warning_on_a_complete_plan(tmp_path):
    loader, _, _ = _load(make_plan(tmp_path / "p.dxf", layers="indian"))
    assert not any("outside the structure" in w for w in loader.load_warnings)


def test_drawn_column_sizes_smaller_than_designed_are_reported():
    from src.design_pipeline import DesignInputs, run_design
    loader, gm, beams = _load(SAMPLES / "plans" / "complex_house.dxf")
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 2, 3.0)
    r = run_design(gm, beams, DesignInputs(num_stories=2, story_height_m=3.0, sbc_kn_m2=150.0, seismic_zone="II"))
    rows = [f for f in r.failures if f["Type"] == "Drawing vs design"]
    assert rows and rows[0]["Status"] == "WARN"
    assert all("drawn 230 x 230" in r["Issue"] for r in rows)
    designed = {r["Issue"].split("designed ")[1].split(" mm")[0] for r in rows}
    assert designed and "230 x 230" not in designed
