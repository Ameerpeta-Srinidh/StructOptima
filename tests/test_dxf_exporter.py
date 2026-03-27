import pytest
import os
import ezdxf
from src.grid_manager import GridManager, Column
from src.framing_logic import StructuralMember
from src.dxf_exporter import ProfessionalDXFExporter

@pytest.fixture
def sample_data():
    gm = GridManager(width_m=6.0, length_m=4.0, num_stories=1)
    gm.x_grid_lines = [0.0, 3.0, 6.0]
    gm.y_grid_lines = [0.0, 4.0]
    c1 = Column(id="C1", x=0, y=0, level=0, width_nb=300, depth_nb=300)
    c2 = Column(id="C2", x=3, y=0, level=0, width_nb=300, depth_nb=300)
    gm.columns = [c1, c2]
    
    b1 = StructuralMember(id="B1", type="beam", 
                          start_point={"x": 0, "y": 0, "z": 0}, 
                          end_point={"x": 3, "y": 0, "z": 0},
                          properties={"width_mm": 230, "depth_mm": 450})
    
    design = {
        "project_name": "Test Project",
        "engineer": "Test Eng",
        "date": "01-01-2026",
        "sheet": "S-1",
        "scale": "1:100"
    }
    
    return gm, [b1], design

def test_prof_dxf_exporter_init(sample_data):
    """Test 1: Verify ProfessionalDXFExporter initializes doc and standard layers correctly."""
    gm, beams, design = sample_data
    exporter = ProfessionalDXFExporter(gm, beams, design, "FOUNDATION")
    
    # Check if layers are created
    layers = [layer.dxf.name for layer in exporter.doc.layers]
    assert "GRID" in layers
    assert "COLUMNS" in layers
    assert "BEAMS" in layers
    assert "TITLE_BLOCK" in layers

def test_prof_dxf_exporter_export(sample_data, tmp_path):
    """Test 2: Verify the export process writes a valid DWG/DXF file without crashing."""
    gm, beams, design = sample_data
    exporter = ProfessionalDXFExporter(gm, beams, design, "FOUNDATION")
    
    out_file = tmp_path / "test_foundation.dxf"
    result = exporter.export(str(out_file))
    
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0

def test_prof_dxf_beam_schedule(sample_data, tmp_path):
    """Test 3: Verify the beam schedule table export works correctly."""
    gm, beams, design = sample_data
    exporter = ProfessionalDXFExporter(gm, beams, design, "FOUNDATION")
    
    out_file = tmp_path / "test_schedule.dxf"
    result = exporter.export_beam_schedule_table(str(out_file))
    
    assert os.path.exists(result)
    assert os.path.getsize(result) > 0
    # verify the file can be parsed
    doc = ezdxf.readfile(result)
    assert len(doc.modelspace()) > 0
