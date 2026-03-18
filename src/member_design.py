"""
Structural Member Design Module - IS 456:2000

Implements design algorithms for beams, columns, and slabs:
- Phase 1: Force enveloping from analysis
- Phase 2: Beam flexure and shear design
- Phase 3: Column P-M interaction
- Phase 4: Slab coefficient method
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import math
import json

from .logging_config import get_logger

logger = get_logger(__name__)


class DesignStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class ReinforcementType(Enum):
    SINGLY = "Singly_Reinforced"
    DOUBLY = "Doubly_Reinforced"


CONCRETE_GRADES = {
    "M20": {"fck": 20, "tau_c_max": 2.8},
    "M25": {"fck": 25, "tau_c_max": 3.1},
    "M30": {"fck": 30, "tau_c_max": 3.5},
    "M35": {"fck": 35, "tau_c_max": 3.7},
    "M40": {"fck": 40, "tau_c_max": 4.0}
}

STEEL_GRADES = {
    "Fe250": {"fy": 250, "xu_d_max": 0.53},
    "Fe415": {"fy": 415, "xu_d_max": 0.48},
    "Fe500": {"fy": 500, "xu_d_max": 0.46}
}

TAU_C_TABLE = [
    (0.15, 0.28), (0.25, 0.36), (0.50, 0.48), (0.75, 0.56),
    (1.00, 0.62), (1.25, 0.67), (1.50, 0.72), (1.75, 0.75),
    (2.00, 0.79), (2.25, 0.81), (2.50, 0.82), (2.75, 0.82),
    (3.00, 0.82)
]


@dataclass
class ForceEnvelope:
    element_id: str
    station_mm: float
    Pu_max_kN: float = 0.0
    Pu_min_kN: float = 0.0
    Mu_max_kNm: float = 0.0
    Mu_min_kNm: float = 0.0
    Vu_max_kN: float = 0.0
    Tu_max_kNm: float = 0.0
    critical_combo: str = ""


@dataclass
class BeamDesignResult:
    element_id: str
    status: DesignStatus
    Mu_kNm: float
    Mu_lim_kNm: float
    reinforcement_type: ReinforcementType
    Ast_tension_mm2: float
    Asc_compression_mm2: float
    tau_v_Nmm2: float
    tau_c_Nmm2: float
    tau_c_max_Nmm2: float
    Vus_kN: float
    stirrup_dia_mm: int
    stirrup_spacing_mm: float
    zone_a_spacing_mm: float
    provided_top: str = ""
    provided_bottom: str = ""
    provided_stirrups: str = ""
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "element_id": self.element_id,
            "status": self.status.value,
            "flexure": {
                "Mu_kNm": round(self.Mu_kNm, 2),
                "Mu_lim_kNm": round(self.Mu_lim_kNm, 2),
                "type": self.reinforcement_type.value,
                "Ast_tension_mm2": round(self.Ast_tension_mm2, 0),
                "Asc_compression_mm2": round(self.Asc_compression_mm2, 0),
                "provided_top": self.provided_top,
                "provided_bottom": self.provided_bottom
            },
            "shear": {
                "tau_v": round(self.tau_v_Nmm2, 3),
                "tau_c": round(self.tau_c_Nmm2, 3),
                "stirrups": self.provided_stirrups
            },
            "warnings": self.warnings
        }


@dataclass
class ColumnDesignResult:
    element_id: str
    status: DesignStatus
    Pu_kN: float
    Mux_kNm: float
    Muy_kNm: float
    slenderness_ratio: float
    is_slender: bool
    e_min_mm: float
    M_design_kNm: float
    interaction_ratio: float
    Ast_mm2: float
    steel_percent: float
    provided_steel: str = ""
    tie_spacing_mm: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "element_id": self.element_id,
            "status": self.status.value,
            "Pu_kN": round(self.Pu_kN, 2),
            "interaction_ratio": round(self.interaction_ratio, 3),
            "slenderness": {
                "ratio": round(self.slenderness_ratio, 2),
                "is_slender": self.is_slender
            },
            "reinforcement": {
                "Ast_mm2": round(self.Ast_mm2, 0),
                "percent": round(self.steel_percent, 2),
                "provided": self.provided_steel
            },
            "ties": f"8mm @ {int(self.tie_spacing_mm)}mm c/c",
            "warnings": self.warnings
        }


@dataclass
class SlabDesignResult:
    element_id: str
    status: DesignStatus
    Mx_kNm_m: float
    My_kNm_m: float
    Ast_x_mm2_m: float
    Ast_y_mm2_m: float
    provided_x: str = ""
    provided_y: str = ""
    deflection_ratio: float = 0.0
    deflection_ok: bool = True
    warnings: List[str] = field(default_factory=list)


class MemberDesigner:
    
    def __init__(
        self,
        concrete_grade: str = "M25",
        steel_grade: str = "Fe415",
        clear_cover_mm: float = 40.0
    ):
        self.concrete = CONCRETE_GRADES.get(concrete_grade, CONCRETE_GRADES["M25"])
        self.steel = STEEL_GRADES.get(steel_grade, STEEL_GRADES["Fe415"])
        self.fck = self.concrete["fck"]
        self.fy = self.steel["fy"]
        self.xu_d_max = self.steel["xu_d_max"]
        self.tau_c_max = self.concrete["tau_c_max"]
        self.clear_cover = clear_cover_mm
        
        logger.info(f"MemberDesigner: {concrete_grade} (fck={self.fck}), "
                   f"{steel_grade} (fy={self.fy})")
    
    def _get_tau_c(self, pt_percent: float) -> float:
        pt = max(0.15, min(pt_percent, 3.0))
        
        for i, (pt_val, tau_c) in enumerate(TAU_C_TABLE):
            if pt <= pt_val:
                if i == 0:
                    return tau_c
                pt_prev, tau_prev = TAU_C_TABLE[i-1]
                ratio = (pt - pt_prev) / (pt_val - pt_prev)
                return tau_prev + ratio * (tau_c - tau_prev)
        
        return TAU_C_TABLE[-1][1]
    
    def calculate_mu_lim(self, b_mm: float, d_mm: float) -> float:
        xu_max = self.xu_d_max * d_mm
        
        Mu_lim = 0.36 * self.fck * b_mm * d_mm**2 * self.xu_d_max * (1 - 0.42 * self.xu_d_max)
        Mu_lim_kNm = Mu_lim / 1e6
        
        return Mu_lim_kNm
    
    def design_beam_flexure(
        self,
        element_id: str,
        b_mm: float,
        D_mm: float,
        Mu_kNm: float,
        bar_dia_mm: float = 16.0
    ) -> Tuple[ReinforcementType, float, float]:
        d = D_mm - self.clear_cover - bar_dia_mm/2
        d_prime = self.clear_cover + bar_dia_mm/2
        
        Mu_lim = self.calculate_mu_lim(b_mm, d)
        
        if Mu_kNm <= Mu_lim:
            Mu = Mu_kNm * 1e6
            
            R = Mu / (b_mm * d**2)
            pt = (self.fck / (2 * self.fy)) * (1 - math.sqrt(1 - 4.598 * R / self.fck)) * 100
            
            pt = max(pt, 0.12 * self.fy / self.fck)
            
            Ast = pt * b_mm * d / 100
            
            logger.info(f"{element_id}: Singly reinforced, Ast={Ast:.0f}mm²")
            return ReinforcementType.SINGLY, Ast, 0.0
        
        else:
            Mu2 = (Mu_kNm - Mu_lim) * 1e6
            
            Ast1 = 0.36 * self.fck * b_mm * self.xu_d_max * d / (0.87 * self.fy)
            
            fsc = 0.87 * self.fy
            Asc = Mu2 / (fsc * (d - d_prime))
            
            Ast2 = Asc * fsc / (0.87 * self.fy)
            Ast = Ast1 + Ast2
            
            logger.info(f"{element_id}: Doubly reinforced, Ast={Ast:.0f}mm², Asc={Asc:.0f}mm²")
            return ReinforcementType.DOUBLY, Ast, Asc
    
    def design_beam_shear(
        self,
        element_id: str,
        b_mm: float,
        D_mm: float,
        Vu_kN: float,
        Ast_mm2: float,
        bar_dia_mm: float = 16.0
    ) -> Tuple[float, float, float, float]:
        d = D_mm - self.clear_cover - bar_dia_mm/2
        
        tau_v = (Vu_kN * 1000) / (b_mm * d)
        
        pt = (Ast_mm2 * 100) / (b_mm * d)
        tau_c = self._get_tau_c(pt)
        
        if tau_v <= tau_c:
            Asv_min = 0.4 * b_mm * d / (0.87 * self.fy)
            sv_max = min(0.75 * d, 300)
            stirrup_dia = 8
            Asv_leg = math.pi * stirrup_dia**2 / 4 * 2
            sv = min(0.87 * self.fy * Asv_leg / (0.4 * b_mm), sv_max)
            
            logger.info(f"{element_id}: Min shear reinforcement, sv={sv:.0f}mm")
            return tau_v, tau_c, 0.0, sv
        
        if tau_v > self.tau_c_max:
            logger.error(f"{element_id}: Shear FAILURE tau_v={tau_v:.2f} > tau_c_max={self.tau_c_max}")
            return tau_v, tau_c, 0.0, 0.0
        
        Vus = (tau_v - tau_c) * b_mm * d / 1000
        
        stirrup_dia = 8
        Asv = math.pi * stirrup_dia**2 / 4 * 2
        sv = 0.87 * self.fy * Asv * d / (Vus * 1000)
        sv = min(sv, 0.75 * d, 300)
        sv = max(50, math.floor(sv / 25) * 25)
        
        logger.info(f"{element_id}: Shear design, tau_v={tau_v:.2f}, sv={sv:.0f}mm")
        return tau_v, tau_c, Vus, sv
    
    def design_beam(
        self,
        element_id: str,
        b_mm: float,
        D_mm: float,
        Mu_kNm: float,
        Vu_kN: float
    ) -> BeamDesignResult:
        d = D_mm - self.clear_cover - 8
        Mu_lim = self.calculate_mu_lim(b_mm, d)
        
        reinf_type, Ast, Asc = self.design_beam_flexure(element_id, b_mm, D_mm, Mu_kNm)
        
        tau_v, tau_c, Vus, sv = self.design_beam_shear(element_id, b_mm, D_mm, Vu_kN, Ast)
        
        zone_a_sv = min(d/4, 100)
        
        status = DesignStatus.PASS
        warnings = []
        
        if tau_v > self.tau_c_max:
            status = DesignStatus.FAIL
            warnings.append(f"Shear failure: tau_v={tau_v:.2f} > tau_c_max={self.tau_c_max}")
        
        if Ast > 0.04 * b_mm * D_mm:
            warnings.append("Steel > 4% - congestion risk")
        
        result = BeamDesignResult(
            element_id=element_id,
            status=status,
            Mu_kNm=Mu_kNm,
            Mu_lim_kNm=Mu_lim,
            reinforcement_type=reinf_type,
            Ast_tension_mm2=Ast,
            Asc_compression_mm2=Asc,
            tau_v_Nmm2=tau_v,
            tau_c_Nmm2=tau_c,
            tau_c_max_Nmm2=self.tau_c_max,
            Vus_kN=Vus,
            stirrup_dia_mm=8,
            stirrup_spacing_mm=sv,
            zone_a_spacing_mm=zone_a_sv,
            warnings=warnings
        )
        
        result.provided_top = self._select_bars(Ast if reinf_type == ReinforcementType.SINGLY else Ast)
        result.provided_bottom = self._select_bars(max(Ast * 0.5, Asc) if Asc > 0 else Ast * 0.5)
        result.provided_stirrups = f"8mm @ {int(zone_a_sv)}mm (Zone A), {int(sv)}mm (Zone B)"
        
        return result
    
    def check_column_slenderness(
        self,
        Leff_mm: float,
        D_mm: float
    ) -> Tuple[float, bool]:
        slenderness = Leff_mm / D_mm
        is_slender = slenderness >= 12
        
        return slenderness, is_slender
    
    def calculate_min_eccentricity(
        self,
        L_mm: float,
        D_mm: float
    ) -> float:
        e_min = L_mm / 500 + D_mm / 30
        e_min = max(e_min, 20)
        
        return e_min
    
    def check_pm_interaction(
        self,
        Pu_kN: float,
        Mux_kNm: float,
        Muy_kNm: float,
        b_mm: float,
        D_mm: float,
        Ast_mm2: float
    ) -> float:
        fck = self.fck
        fy = self.fy
        
        Puz = 0.45 * fck * b_mm * D_mm + 0.75 * fy * Ast_mm2
        Puz_kN = Puz / 1000
        
        Pu_Puz = Pu_kN / Puz_kN if Puz_kN > 0 else 1.0
        
        if Pu_Puz <= 0.2:
            alpha_n = 1.0
        elif Pu_Puz >= 0.8:
            alpha_n = 2.0
        else:
            alpha_n = 1.0 + (Pu_Puz - 0.2) / 0.6
        
        d_x = D_mm - self.clear_cover - 8
        d_y = b_mm - self.clear_cover - 8
        
        Mux1 = 0.36 * fck * b_mm * d_x**2 * 0.48 * (1 - 0.42 * 0.48) / 1e6
        Muy1 = 0.36 * fck * D_mm * d_y**2 * 0.48 * (1 - 0.42 * 0.48) / 1e6
        
        Mux1 = max(Mux1, 1.0)
        Muy1 = max(Muy1, 1.0)
        
        ratio = (abs(Mux_kNm) / Mux1)**alpha_n + (abs(Muy_kNm) / Muy1)**alpha_n
        
        return ratio
    
    def design_column(
        self,
        element_id: str,
        b_mm: float,
        D_mm: float,
        L_mm: float,
        Pu_kN: float,
        Mux_kNm: float,
        Muy_kNm: float,
        steel_percent: float = 1.0
    ) -> ColumnDesignResult:
        slenderness, is_slender = self.check_column_slenderness(L_mm, min(b_mm, D_mm))
        
        e_min = self.calculate_min_eccentricity(L_mm, D_mm)
        M_min_x = Pu_kN * e_min / 1000
        M_min_y = Pu_kN * e_min / 1000
        
        Mux_design = max(abs(Mux_kNm), M_min_x)
        Muy_design = max(abs(Muy_kNm), M_min_y)
        
        if is_slender:
            e_add = L_mm**2 / (2000 * D_mm)
            M_add = Pu_kN * e_add / 1000
            Mux_design += M_add
        
        Ast = steel_percent * b_mm * D_mm / 100
        
        interaction_ratio = self.check_pm_interaction(
            Pu_kN, Mux_design, Muy_design, b_mm, D_mm, Ast
        )
        
        if interaction_ratio <= 1.0:
            status = DesignStatus.PASS
        else:
            status = DesignStatus.FAIL
        
        warnings = []
        if is_slender:
            warnings.append(f"Slender column (λ={slenderness:.1f}) - additional moment applied")
        if steel_percent < 0.8:
            warnings.append("Steel < 0.8% minimum per IS 456")
        if steel_percent > 4.0:
            warnings.append("Steel > 4% maximum per IS 456")
        
        tie_spacing = min(min(b_mm, D_mm), 16 * 16, 300)
        
        result = ColumnDesignResult(
            element_id=element_id,
            status=status,
            Pu_kN=Pu_kN,
            Mux_kNm=Mux_design,
            Muy_kNm=Muy_design,
            slenderness_ratio=slenderness,
            is_slender=is_slender,
            e_min_mm=e_min,
            M_design_kNm=max(Mux_design, Muy_design),
            interaction_ratio=interaction_ratio,
            Ast_mm2=Ast,
            steel_percent=steel_percent,
            tie_spacing_mm=tie_spacing,
            warnings=warnings
        )
        
        result.provided_steel = self._select_column_bars(Ast)
        
        return result
    
    def design_slab(
        self,
        element_id: str,
        Lx_mm: float,
        Ly_mm: float,
        thickness_mm: float,
        w_kN_m2: float,
        edge_condition: str = "two_adjacent_continuous"
    ) -> SlabDesignResult:
        ratio = Ly_mm / Lx_mm
        
        COEFFICIENTS = {
            "all_edges_continuous": {"alpha_x_neg": 0.032, "alpha_x_pos": 0.024, "alpha_y_neg": 0.032, "alpha_y_pos": 0.024},
            "two_adjacent_continuous": {"alpha_x_neg": 0.047, "alpha_x_pos": 0.035, "alpha_y_neg": 0.045, "alpha_y_pos": 0.035},
            "one_long_continuous": {"alpha_x_neg": 0.037, "alpha_x_pos": 0.028, "alpha_y_neg": 0.037, "alpha_y_pos": 0.028},
            "all_edges_discontinuous": {"alpha_x_neg": 0.0, "alpha_x_pos": 0.056, "alpha_y_neg": 0.0, "alpha_y_pos": 0.056}
        }
        
        coeff = COEFFICIENTS.get(edge_condition, COEFFICIENTS["two_adjacent_continuous"])
        
        alpha_x = max(coeff["alpha_x_neg"], coeff["alpha_x_pos"])
        alpha_y = max(coeff["alpha_y_neg"], coeff["alpha_y_pos"])
        
        Mx = alpha_x * w_kN_m2 * (Lx_mm/1000)**2
        My = alpha_y * w_kN_m2 * (Lx_mm/1000)**2
        
        d = thickness_mm - self.clear_cover - 5
        
        Ast_x = self._calculate_slab_steel(Mx, d)
        Ast_y = self._calculate_slab_steel(My, d - 10)
        
        Ast_min = 0.12 * 1000 * thickness_mm / 100
        Ast_x = max(Ast_x, Ast_min)
        Ast_y = max(Ast_y, Ast_min)
        
        basic_ld = 26
        mod_factor = 1.5
        ld_limit = basic_ld * mod_factor
        actual_ld = Lx_mm / d
        deflection_ok = actual_ld <= ld_limit
        
        status = DesignStatus.PASS if deflection_ok else DesignStatus.WARNING
        warnings = []
        if not deflection_ok:
            warnings.append(f"L/d={actual_ld:.1f} > limit={ld_limit:.1f}")
        
        result = SlabDesignResult(
            element_id=element_id,
            status=status,
            Mx_kNm_m=Mx,
            My_kNm_m=My,
            Ast_x_mm2_m=Ast_x,
            Ast_y_mm2_m=Ast_y,
            deflection_ratio=actual_ld,
            deflection_ok=deflection_ok,
            warnings=warnings
        )
        
        result.provided_x = self._select_slab_bars(Ast_x)
        result.provided_y = self._select_slab_bars(Ast_y)
        
        return result
    
    def _calculate_slab_steel(self, Mu_kNm_m: float, d_mm: float) -> float:
        b = 1000
        Mu = Mu_kNm_m * 1e6
        
        R = Mu / (b * d_mm**2)
        pt = (self.fck / (2 * self.fy)) * (1 - math.sqrt(max(0, 1 - 4.598 * R / self.fck))) * 100
        
        Ast = pt * b * d_mm / 100
        return Ast
    
    def _select_bars(self, Ast_mm2: float) -> str:
        bar_options = [
            (12, 113.1), (16, 201.1), (20, 314.2), (25, 490.9)
        ]
        
        for dia, area in bar_options:
            n_bars = math.ceil(Ast_mm2 / area)
            if n_bars <= 4:
                return f"{n_bars}-T{dia}"
        
        return f"{math.ceil(Ast_mm2 / 490.9)}-T25"
    
    def _select_column_bars(self, Ast_mm2: float) -> str:
        bar_area = 201.1
        n_bars = max(4, math.ceil(Ast_mm2 / bar_area))
        n_bars = ((n_bars + 3) // 4) * 4
        
        return f"{n_bars}-T16"
    
    def _select_slab_bars(self, Ast_mm2_m: float) -> str:
        bar_options = [(8, 50.3), (10, 78.5), (12, 113.1)]
        
        for dia, area in bar_options:
            spacing = 1000 * area / Ast_mm2_m
            if spacing >= 100:
                spacing = min(300, max(100, int(spacing / 25) * 25))
                return f"T{dia} @ {spacing}mm c/c"
        
        return f"T12 @ 100mm c/c"
