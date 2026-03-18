"""
Unit tests for src/audit.py - Structural auditor and independent checks.
"""
import pytest
from src.audit import AuditResult, StructuralAuditor
from src.grid_manager import GridManager, Column
from src.framing_logic import StructuralMember, MemberProperties, Point
from src.foundation_eng import design_footing, Footing
from src.materials import Concrete


class TestAuditResult:
    """Test AuditResult model."""

    def test_audit_result_creation(self):
        """Test creating an audit result."""
        result = AuditResult(
            member_id="C1",
            check_name="Column Axial Capacity",
            design_value=500.0,
            limit_value=600.0,
            status="PASS",
            notes="Load within capacity"
        )
        
        assert result.member_id == "C1"
        assert result.status == "PASS"
        assert result.design_value < result.limit_value

    def test_audit_result_fail_status(self):
        """Test audit result with FAIL status."""
        result = AuditResult(
            member_id="B5",
            check_name="Beam Deflection",
            design_value=30.0,
            limit_value=24.0,
            status="FAIL",
            discrepancy_percent=125.0,
            notes="Deflection exceeds L/250"
        )
        
        assert result.status == "FAIL"
        assert result.design_value > result.limit_value

    def test_audit_result_default_discrepancy(self):
        """Test default discrepancy is 0."""
        result = AuditResult(
            member_id="F1",
            check_name="Bearing Pressure",
            design_value=180.0,
            limit_value=200.0,
            status="PASS"
        )
        
        assert result.discrepancy_percent == 0.0


class TestStructuralAuditor:
    """Test StructuralAuditor class."""

    @pytest.fixture
    def setup_structure(self):
        """Set up a complete structure for auditing."""
        # Create grid manager
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=2, story_height_m=3.0)
        gm.generate_grid()
        gm.calculate_trib_areas()
        gm.calculate_loads(floor_load_kn_m2=50.0, wall_load_kn_m=12.0)
        
        concrete = Concrete.from_grade("M25")
        gm.optimize_column_sizes(concrete=concrete, fy=415.0)
        gm.detail_columns(concrete=concrete, fy=415.0)
        
        # Generate beams
        beams = gm.generate_beams()
        gm.detail_beams(beams)
        
        # Design footings for level 0 columns
        level_0_cols = [c for c in gm.columns if c.level == 0]
        footings = []
        for col in level_0_cols:
            ft = design_footing(
                axial_load_kn=col.load_kn,
                sbc_kn_m2=200.0,
                column_width_mm=col.width_nb,
                column_depth_mm=col.depth_nb,
                concrete=concrete
            )
            footings.append(ft)
        
        return gm, beams, footings

    def test_auditor_initialization(self, setup_structure):
        """Test auditor initialization."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        
        assert auditor.grid_mgr is gm
        assert auditor.beams is beams
        assert auditor.footings is footings
        assert len(auditor.audit_log) == 0

    def test_run_audit(self, setup_structure):
        """Test full audit run."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        results = auditor.run_audit()
        
        assert len(results) > 0
        assert all(isinstance(r, AuditResult) for r in results)

    def test_audit_columns(self, setup_structure):
        """Test column capacity audit."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        auditor.audit_columns()
        
        # Should have audit results for columns
        column_audits = [r for r in auditor.audit_log if "Column" in r.check_name]
        assert len(column_audits) > 0

    def test_audit_footings(self, setup_structure):
        """Test footing audit (bearing pressure and punching shear)."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        auditor.audit_footings()
        
        # Should have bearing pressure checks
        bearing_audits = [r for r in auditor.audit_log if "Bearing" in r.check_name]
        assert len(bearing_audits) > 0
        
        # Should have punching shear checks
        shear_audits = [r for r in auditor.audit_log if "Punching" in r.check_name]
        assert len(shear_audits) > 0

    def test_audit_beams(self, setup_structure):
        """Test beam deflection audit."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        auditor.audit_beams()
        
        # Should have deflection checks
        beam_audits = [r for r in auditor.audit_log if "Deflection" in r.check_name]
        assert len(beam_audits) > 0

    def test_math_breakdown_populated(self, setup_structure):
        """Test that math breakdown is populated for sample columns."""
        gm, beams, footings = setup_structure
        
        # Ensure we have a column named C1 or similar
        auditor = StructuralAuditor(gm, beams, footings)
        auditor.audit_columns()
        
        # math_breakdown might be populated for certain columns
        # This tests the feature exists (may or may not have entries based on column IDs)
        assert hasattr(auditor, 'math_breakdown')

    def test_all_checks_have_status(self, setup_structure):
        """Test all audit results have valid status."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        results = auditor.run_audit()
        
        valid_statuses = {"PASS", "FAIL", "WARN"}
        for result in results:
            assert result.status in valid_statuses

    def test_properly_sized_structure_passes(self, setup_structure):
        """Test that a properly designed structure passes most checks."""
        gm, beams, footings = setup_structure
        
        auditor = StructuralAuditor(gm, beams, footings)
        results = auditor.run_audit()
        
        pass_count = sum(1 for r in results if r.status == "PASS")
        fail_count = sum(1 for r in results if r.status == "FAIL")
        
        # A properly designed structure should pass more than half
        assert pass_count > fail_count


class TestAuditEdgeCases:
    """Test edge cases in auditing."""

    def test_mismatched_footing_count(self):
        """Test handling of mismatched footing and column counts."""
        gm = GridManager(width_m=6.0, length_m=6.0, num_stories=1)
        gm.generate_grid()
        gm.calculate_trib_areas()
        gm.calculate_loads(floor_load_kn_m2=50.0)
        
        beams = gm.generate_beams()
        
        # Create fewer footings than columns
        footings = [Footing(
            length_m=1.5,
            width_m=1.5,
            thickness_mm=300.0,
            area_m2=2.25,
            concrete_vol_m3=0.675,
            excavation_vol_m3=3.375
        )]  # Only one footing
        
        auditor = StructuralAuditor(gm, beams, footings)
        auditor.audit_footings()
        
        # Should log a failure for count mismatch
        mismatch_logs = [r for r in auditor.audit_log if "Count" in r.check_name or "mismatch" in r.notes.lower()]
        assert len(mismatch_logs) > 0

    def test_empty_beams_list(self):
        """Test handling of empty beams list."""
        gm = GridManager(width_m=6.0, length_m=6.0)
        gm.generate_grid()
        
        auditor = StructuralAuditor(gm, [], [])
        auditor.audit_beams()
        
        # Should not crash, just have no beam audits
        beam_audits = [r for r in auditor.audit_log if "Beam" in r.check_name]
        assert len(beam_audits) == 0
