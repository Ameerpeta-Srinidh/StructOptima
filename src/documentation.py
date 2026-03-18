"""
Documentation Module - Structural Calculation Reports

Generates structural design reports including:
- Model Validation (Modal Mass, Frequency)
- Drift Checks (Inter-storey drift)
- Sample Calculations (Transparent "White Box" trace)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import math
from datetime import datetime

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ModelValidationResult:
    modal_mass_participation_percent: float
    fundamental_frequency_hz: float
    is_valid: bool
    warnings: List[str] = field(default_factory=list)


@dataclass
class DriftCheckResult:
    storey: str
    drift_mm: float
    height_mm: float
    ratio: float
    limit_ratio: float = 0.004  # H/250 or 0.004H
    status: str = "PASS"


@dataclass
class SampleCalculation:
    title: str
    element_id: str
    steps: List[str]
    reference_code: str


class DesignReportGenerator:
    
    def __init__(self, project_name: str, engineer_name: str):
        self.project_name = project_name
        self.engineer_name = engineer_name
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.validation_result: Optional[ModelValidationResult] = None
        self.drift_checks: List[DriftCheckResult] = []
        self.sample_calcs: List[SampleCalculation] = []
        
    def validate_model(
        self, 
        modal_mass_percent: float, 
        freq_hz: float
    ) -> ModelValidationResult:
        """
        Validate FEA model against code requirements.
        IS 1893: Modal mass > 90%
        """
        warnings = []
        is_valid = True
        
        if modal_mass_percent < 90.0:
            warnings.append(f"Modal mass participation {modal_mass_percent}% < 90% (IS 1893 Cl 7.7.5.2)")
            is_valid = False
            
        if freq_hz <= 0:
            warnings.append("Fundamental frequency must be positive")
            is_valid = False
            
        self.validation_result = ModelValidationResult(
            modal_mass_participation_percent=modal_mass_percent,
            fundamental_frequency_hz=freq_hz,
            is_valid=is_valid,
            warnings=warnings
        )
        return self.validation_result

    def check_storey_drift(
        self, 
        storey: str, 
        drift_mm: float, 
        height_mm: float,
        limit_ratio: float = 0.004
    ):
        """
        Check inter-storey drift against IS 1893 limits.
        """
        ratio = drift_mm / height_mm if height_mm > 0 else 0
        status = "PASS" if ratio <= limit_ratio else "FAIL"
        
        self.drift_checks.append(DriftCheckResult(
            storey=storey,
            drift_mm=drift_mm,
            height_mm=height_mm,
            ratio=ratio,
            limit_ratio=limit_ratio,
            status=status
        ))

    def add_sample_calculation(self, title: str, element_id: str, steps: List[str], code_ref: str):
        """Add a transparent calculation trace."""
        self.sample_calcs.append(SampleCalculation(
            title=title,
            element_id=element_id,
            steps=steps,
            reference_code=code_ref
        ))

    def generate_report(self) -> str:
        """Generate formatted report."""
        lines = []
        lines.append("="*60)
        lines.append(f"STRUCTURAL DESIGN REPORT: {self.project_name}")
        lines.append(f"Engineer: {self.engineer_name}")
        lines.append(f"Date: {self.timestamp}")
        lines.append("="*60)
        lines.append("")
        
        # 1. Model Validation
        lines.append("1. MODEL VALIDATION")
        lines.append("-" * 30)
        if self.validation_result:
            res = self.validation_result
            status = "VALID" if res.is_valid else "INVALID"
            lines.append(f"Status: {status}")
            lines.append(f"Modal Mass Participation: {res.modal_mass_participation_percent}%")
            lines.append(f"Fundamental Frequency: {res.fundamental_frequency_hz} Hz")
            for w in res.warnings:
                lines.append(f"Warning: {w}")
        else:
            lines.append("No validation data.")
        lines.append("")
        
        # 2. Drift Checks
        lines.append("2. INTER-STOREY DRIFT CHECKS (IS 1893)")
        lines.append("-" * 30)
        lines.append(f"{'Storey':<10} | {'Drift(mm)':<10} | {'Height(mm)':<10} | {'Ratio':<10} | {'Status'}")
        for d in self.drift_checks:
            lines.append(f"{d.storey:<10} | {d.drift_mm:<10.2f} | {d.height_mm:<10.0f} | {d.ratio:<10.5f} | {d.status}")
        lines.append("")
        
        # 3. Sample Calculations
        lines.append("3. SAMPLE CALCULATIONS (WHITE BOX)")
        lines.append("-" * 30)
        for calc in self.sample_calcs:
            lines.append(f"Title: {calc.title}")
            lines.append(f"Element: {calc.element_id}")
            lines.append(f"Ref: {calc.reference_code}")
            lines.append("Steps:")
            for step in calc.steps:
                lines.append(f"  - {step}")
            lines.append("-" * 20)
            
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({
            "project": self.project_name,
            "validation": self.validation_result.__dict__ if self.validation_result else None,
            "drift_checks": [d.__dict__ for d in self.drift_checks],
            "sample_calcs": [c.__dict__ for c in self.sample_calcs]
        }, indent=2)
