"""
Anchorage and Development Length Module - IS 456:2000

Calculates development length (Ld) and lap length per IS 456 Cl 26.2.
Critical for ensuring proper bond between reinforcement and concrete.

Reference: IS 456:2000 Clause 26.2
"""

from dataclasses import dataclass
from typing import Dict, Tuple
from enum import Enum


class BarPosition(str, Enum):
    """Bar position affecting bond stress."""
    BOTTOM = "bottom"  # Bars in bottom third of section
    TOP = "top"        # Bars in top third (reduced bond due to bleeding)
    OTHER = "other"    # Intermediate positions


class StressType(str, Enum):
    """Type of stress in the bar."""
    TENSION = "tension"
    COMPRESSION = "compression"


@dataclass
class DevelopmentLengthResult:
    """Result of development length calculation."""
    bar_dia_mm: int
    fy_mpa: float
    fck_mpa: float
    
    # Bond stress
    tau_bd_mpa: float  # Design bond stress
    
    # Development length
    Ld_mm: float       # Basic development length
    Ld_provided_mm: float  # Rounded up to practical value
    
    # Lap length
    lap_tension_mm: float
    lap_compression_mm: float
    
    # Anchorage
    standard_hook_mm: float  # 90° hook equivalent
    
    # Verification
    formula_used: str


# IS 456 Table 8 - Design Bond Stress (τbd) in MPa
# For plain bars in tension (multiply by 1.6 for deformed bars)
BOND_STRESS_TABLE = {
    # fck: τbd for plain bars
    15: 1.0,
    20: 1.2,
    25: 1.4,
    30: 1.5,
    35: 1.7,
    40: 1.9,
}


class AnchorageCalculator:
    """
    IS 456:2000 Anchorage and Development Length Calculator.
    
    Reference: IS 456:2000, Clause 26.2
    """
    
    def __init__(
        self,
        fck: float = 25.0,  # Concrete grade (MPa)
        fy: float = 500.0,  # Steel grade (MPa)
        deformed_bars: bool = True  # Use deformed bars (HYSD)
    ):
        self.fck = fck
        self.fy = fy
        self.deformed_bars = deformed_bars
        
        # Get bond stress from table
        self.tau_bd = self._get_bond_stress()
    
    def _get_bond_stress(self) -> float:
        """
        Get design bond stress per IS 456 Table 8.
        
        For deformed bars: multiply by 1.6
        For bars in compression: multiply by 1.25
        """
        # Find nearest fck in table
        fck_key = min(BOND_STRESS_TABLE.keys(), key=lambda x: abs(x - self.fck))
        tau_bd = BOND_STRESS_TABLE[fck_key]
        
        # Increase for deformed bars (IS 456 Cl 26.2.1.1)
        if self.deformed_bars:
            tau_bd *= 1.6
        
        return tau_bd
    
    def calculate_development_length(
        self,
        bar_dia_mm: int,
        stress_type: StressType = StressType.TENSION,
        position: BarPosition = BarPosition.BOTTOM
    ) -> DevelopmentLengthResult:
        """
        Calculate development length per IS 456 Cl 26.2.1.
        
        Ld = (Φ × σs) / (4 × τbd)
        
        Where:
            Φ = nominal diameter of bar
            σs = stress in bar = 0.87 × fy
            τbd = design bond stress (IS 456 Table 8)
        
        Args:
            bar_dia_mm: Bar diameter in mm
            stress_type: Tension or compression
            position: Bar position in section
            
        Returns:
            DevelopmentLengthResult with all values
        """
        phi = bar_dia_mm
        sigma_s = 0.87 * self.fy  # Design stress in steel
        
        # Bond stress adjustment for compression
        tau_bd = self.tau_bd
        if stress_type == StressType.COMPRESSION:
            tau_bd *= 1.25  # IS 456 Cl 26.2.1.1
        
        # Development length formula (IS 456 Cl 26.2.1)
        Ld = (phi * sigma_s) / (4 * tau_bd)
        
        # Round up to nearest 50mm for practical use
        Ld_provided = ((int(Ld) // 50) + 1) * 50
        
        # Lap length (IS 456 Cl 26.2.5)
        # Tension: Ld or 30Φ, whichever is greater
        # Compression: 0.8 × Ld or 24Φ, whichever is greater
        if stress_type == StressType.TENSION:
            lap_tension = max(Ld, 30 * phi)
            lap_compression = max(0.8 * Ld, 24 * phi)
        else:
            lap_tension = max(Ld, 30 * phi)
            lap_compression = max(0.8 * Ld, 24 * phi)
        
        # Round to nearest 50mm
        lap_tension = ((int(lap_tension) // 50) + 1) * 50
        lap_compression = ((int(lap_compression) // 50) + 1) * 50
        
        # Standard hook equivalent (IS 456 Cl 26.2.2.1)
        # 90° bend: 8Φ beyond bend + hook
        # Equivalent anchorage = 8Φ for 45° bend, 16Φ for 90° bend
        standard_hook = 16 * phi
        
        formula = f"Ld = (Φ × 0.87fy) / (4 × τbd) = ({phi} × {sigma_s:.0f}) / (4 × {tau_bd:.2f})"
        
        return DevelopmentLengthResult(
            bar_dia_mm=bar_dia_mm,
            fy_mpa=self.fy,
            fck_mpa=self.fck,
            tau_bd_mpa=tau_bd,
            Ld_mm=Ld,
            Ld_provided_mm=Ld_provided,
            lap_tension_mm=lap_tension,
            lap_compression_mm=lap_compression,
            standard_hook_mm=standard_hook,
            formula_used=formula
        )
    
    def get_all_bar_lengths(self) -> Dict[int, DevelopmentLengthResult]:
        """
        Calculate development lengths for all standard bar diameters.
        
        Returns:
            Dictionary mapping bar diameter to results
        """
        standard_bars = [8, 10, 12, 16, 20, 25, 32]
        results = {}
        
        for dia in standard_bars:
            results[dia] = self.calculate_development_length(dia)
        
        return results
    
    def generate_summary_table(self) -> str:
        """Generate a summary table for reports."""
        all_lengths = self.get_all_bar_lengths()
        
        lines = [
            f"Development & Lap Length Schedule (IS 456:2000)",
            f"Concrete: M{int(self.fck)} | Steel: Fe{int(self.fy)} | Bond Stress: {self.tau_bd:.2f} MPa",
            "",
            "| Bar Φ | Ld (mm) | Lap (Tension) | Lap (Comp) | Hook |",
            "|-------|---------|---------------|------------|------|",
        ]
        
        for dia, result in all_lengths.items():
            lines.append(
                f"| {dia}mm | {result.Ld_provided_mm:.0f} | "
                f"{result.lap_tension_mm:.0f} | {result.lap_compression_mm:.0f} | "
                f"{result.standard_hook_mm:.0f} |"
            )
        
        return "\n".join(lines)


def get_development_length_table(
    fck: float = 25.0,
    fy: float = 500.0
) -> Dict[int, DevelopmentLengthResult]:
    """
    Convenience function to get development length for all bar sizes.
    
    Args:
        fck: Concrete grade
        fy: Steel grade
        
    Returns:
        Dictionary of bar diameter -> DevelopmentLengthResult
    """
    calc = AnchorageCalculator(fck=fck, fy=fy)
    return calc.get_all_bar_lengths()


def get_lap_length(
    bar_dia_mm: int,
    stress_type: str = "tension",
    fck: float = 25.0,
    fy: float = 500.0
) -> int:
    """
    Quick function to get lap length for a specific bar.
    
    Args:
        bar_dia_mm: Bar diameter
        stress_type: "tension" or "compression"
        fck: Concrete grade
        fy: Steel grade
        
    Returns:
        Lap length in mm
    """
    calc = AnchorageCalculator(fck=fck, fy=fy)
    st = StressType.TENSION if stress_type == "tension" else StressType.COMPRESSION
    result = calc.calculate_development_length(bar_dia_mm, st)
    
    if stress_type == "tension":
        return int(result.lap_tension_mm)
    return int(result.lap_compression_mm)
