"""
Analysis Model Configuration Module - IS 1893:2016 & IS 16700

Configures structural analysis parameters:
- Phase 1: Lateral load parameters (seismic Z, R, I; wind Vb, k factors)
- Phase 2: Seismic mass calculation (DL + reduced LL)
- Phase 3: Stiffness modifiers (cracked sections)
- Phase 4: Load combination generation (26+ cases)
- Phase 5: P-Delta and diaphragm settings
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import json
import math

from .logging_config import get_logger
from .load_combinations import LoadCombinationManager, LoadType, LoadCombination, CombinationType

logger = get_logger(__name__)


class StructuralFrameType(Enum):
    SMRF = "SMRF"
    OMRF = "OMRF"
    DUAL = "Dual"
    SHEAR_WALL = "Shear_Wall"


class DiaphragmType(Enum):
    RIGID = "Rigid"
    SEMI_RIGID = "Semi_Rigid"
    FLEXIBLE = "Flexible"


class SoilType(Enum):
    TYPE_I = "I"
    TYPE_II = "II"
    TYPE_III = "III"


ZONE_FACTORS = {
    "II": 0.10,
    "III": 0.16,
    "IV": 0.24,
    "V": 0.36
}

RESPONSE_REDUCTION = {
    StructuralFrameType.SMRF: 5.0,
    StructuralFrameType.OMRF: 3.0,
    StructuralFrameType.DUAL: 4.0,
    StructuralFrameType.SHEAR_WALL: 4.0
}

SA_G_VALUES = {
    SoilType.TYPE_I: {"T_limit": 0.40, "Sa_max": 2.5},
    SoilType.TYPE_II: {"T_limit": 0.55, "Sa_max": 2.5},
    SoilType.TYPE_III: {"T_limit": 0.67, "Sa_max": 2.5}
}


@dataclass
class SeismicParameters:
    zone: str
    zone_factor: float
    response_reduction: float
    importance_factor: float
    soil_type: SoilType
    frame_type: StructuralFrameType
    
    def to_dict(self) -> Dict:
        return {
            "zone": self.zone,
            "Z": self.zone_factor,
            "R": self.response_reduction,
            "I": self.importance_factor,
            "soil_type": self.soil_type.value,
            "frame_type": self.frame_type.value
        }


@dataclass
class StiffnessModifiers:
    columns: float = 0.70
    beams: float = 0.35
    slabs: float = 0.25
    shear_walls: float = 0.70
    
    def to_dict(self) -> Dict:
        return {
            "columns": self.columns,
            "beams": self.beams,
            "slabs": self.slabs,
            "shear_walls": self.shear_walls
        }


@dataclass
class PDeltaSettings:
    enabled: bool = True
    iterations: int = 3
    tolerance: float = 0.001
    reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "enabled": self.enabled,
            "iterations": self.iterations,
            "tolerance": self.tolerance,
            "reason": self.reason
        }


@dataclass
class SeismicMassConfig:
    dead_load_factor: float = 1.0
    live_load_upto_3kn: float = 0.25
    live_load_above_3kn: float = 0.50
    roof_live_load: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "dead_load_factor": self.dead_load_factor,
            "live_load_upto_3kn": self.live_load_upto_3kn,
            "live_load_above_3kn": self.live_load_above_3kn,
            "roof_live_load": self.roof_live_load
        }


@dataclass
class FloorMass:
    floor_id: str
    level_m: float
    dead_load_kn: float
    live_load_kn: float
    live_load_intensity_kn_m2: float
    is_roof: bool
    effective_live_load_kn: float = 0.0
    seismic_mass_kn: float = 0.0


@dataclass
class AnalysisConfig:
    seismic_params: SeismicParameters
    stiffness_modifiers: StiffnessModifiers
    p_delta: PDeltaSettings
    seismic_mass: SeismicMassConfig
    diaphragm_type: DiaphragmType
    load_combinations: List[Dict]
    floor_masses: List[FloorMass] = field(default_factory=list)
    total_seismic_weight_kn: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "analysis_config": {
                "seismic_parameters": self.seismic_params.to_dict(),
                "stiffness_modifiers": self.stiffness_modifiers.to_dict(),
                "p_delta_effect": self.p_delta.to_dict(),
                "seismic_mass_source": self.seismic_mass.to_dict(),
                "diaphragm_type": self.diaphragm_type.value,
                "total_seismic_weight_kn": round(self.total_seismic_weight_kn, 2)
            },
            "load_combinations": self.load_combinations,
            "floor_masses": [
                {
                    "floor": fm.floor_id,
                    "level_m": fm.level_m,
                    "seismic_mass_kn": round(fm.seismic_mass_kn, 2)
                }
                for fm in self.floor_masses
            ],
            "warnings": self.warnings
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AnalysisConfigGenerator:
    
    def __init__(
        self,
        zone: str = "III",
        soil_type: str = "II",
        frame_type: str = "SMRF",
        importance_factor: float = 1.0,
        num_storeys: int = 4,
        storey_height_m: float = 3.0,
        plan_cutout_percent: float = 0.0,
        include_wind: bool = True,
        include_vertical_seismic: bool = False
    ):
        self.zone = zone
        self.soil_type = SoilType(soil_type) if isinstance(soil_type, str) else soil_type
        self.frame_type = StructuralFrameType[frame_type] if isinstance(frame_type, str) else frame_type
        self.importance_factor = importance_factor
        self.num_storeys = num_storeys
        self.storey_height_m = storey_height_m
        self.plan_cutout_percent = plan_cutout_percent
        self.include_wind = include_wind
        self.include_vertical_seismic = include_vertical_seismic
        
        self.floor_masses: List[FloorMass] = []
        self.warnings: List[str] = []
        
        self._validate_and_adjust()
    
    def _validate_and_adjust(self):
        if self.zone in ["III", "IV", "V"]:
            if self.frame_type == StructuralFrameType.OMRF:
                self.warnings.append(
                    f"Zone {self.zone} requires SMRF (R=5) for residential buildings. "
                    f"Changing from OMRF to SMRF per IS 1893."
                )
                self.frame_type = StructuralFrameType.SMRF
                logger.warning("Forcing SMRF for seismic zone III+")
    
    def _configure_seismic_parameters(self) -> SeismicParameters:
        zone_factor = ZONE_FACTORS.get(self.zone, 0.16)
        r_factor = RESPONSE_REDUCTION.get(self.frame_type, 5.0)
        
        params = SeismicParameters(
            zone=self.zone,
            zone_factor=zone_factor,
            response_reduction=r_factor,
            importance_factor=self.importance_factor,
            soil_type=self.soil_type,
            frame_type=self.frame_type
        )
        
        logger.info(f"Seismic: Zone {self.zone} (Z={zone_factor}), "
                   f"{self.frame_type.value} (R={r_factor}), I={self.importance_factor}")
        
        return params
    
    def _configure_stiffness_modifiers(self) -> StiffnessModifiers:
        modifiers = StiffnessModifiers(
            columns=0.70,
            beams=0.35,
            slabs=0.25,
            shear_walls=0.70
        )
        
        logger.info("Stiffness modifiers (IS 1893 Cl 6.4.3): "
                   f"Columns=0.70I, Beams=0.35I, Slabs=0.25I")
        
        return modifiers
    
    def _configure_p_delta(self) -> PDeltaSettings:
        enabled = self.num_storeys > 4
        
        if enabled:
            reason = f"Building height {self.num_storeys} storeys > 4 - P-Delta effects significant"
        else:
            reason = f"Building height {self.num_storeys} storeys <= 4 - P-Delta optional"
        
        settings = PDeltaSettings(
            enabled=enabled,
            iterations=3,
            tolerance=0.001,
            reason=reason
        )
        
        if enabled:
            logger.info(f"P-Delta enabled: {reason}")
        
        return settings
    
    def _configure_seismic_mass(self) -> SeismicMassConfig:
        return SeismicMassConfig(
            dead_load_factor=1.0,
            live_load_upto_3kn=0.25,
            live_load_above_3kn=0.50,
            roof_live_load=0.0
        )
    
    def _determine_diaphragm_type(self) -> DiaphragmType:
        if self.plan_cutout_percent > 30:
            self.warnings.append(
                f"Plan cutout {self.plan_cutout_percent}% > 30% - "
                "Using semi-rigid diaphragm. Review force distribution."
            )
            logger.warning("Large plan cutout - switching to semi-rigid diaphragm")
            return DiaphragmType.SEMI_RIGID
        elif self.plan_cutout_percent > 50:
            return DiaphragmType.FLEXIBLE
        
        return DiaphragmType.RIGID
    
    def add_floor_mass(
        self,
        floor_id: str,
        level_m: float,
        dead_load_kn: float,
        live_load_kn: float,
        live_load_intensity_kn_m2: float,
        is_roof: bool = False
    ):
        mass_config = self._configure_seismic_mass()
        
        if is_roof:
            reduction_factor = mass_config.roof_live_load
        elif live_load_intensity_kn_m2 <= 3.0:
            reduction_factor = mass_config.live_load_upto_3kn
        else:
            reduction_factor = mass_config.live_load_above_3kn
        
        effective_ll = live_load_kn * reduction_factor
        seismic_mass = dead_load_kn + effective_ll
        
        floor_mass = FloorMass(
            floor_id=floor_id,
            level_m=level_m,
            dead_load_kn=dead_load_kn,
            live_load_kn=live_load_kn,
            live_load_intensity_kn_m2=live_load_intensity_kn_m2,
            is_roof=is_roof,
            effective_live_load_kn=effective_ll,
            seismic_mass_kn=seismic_mass
        )
        
        self.floor_masses.append(floor_mass)
        logger.info(f"Floor {floor_id}: DL={dead_load_kn:.0f}kN, "
                   f"LL={live_load_kn:.0f}kN ({reduction_factor*100:.0f}% used), "
                   f"Seismic Mass={seismic_mass:.0f}kN")
    
    def _generate_load_combinations(self) -> List[Dict]:
        combinations = []
        combo_id = 1
        
        combinations.append({
            "id": f"UDCON{combo_id}",
            "name": "1.5(DL+LL)",
            "factors": {"DL": 1.5, "LL": 1.5},
            "type": "Strength",
            "code_ref": "IS 456 Table 18"
        })
        combo_id += 1
        
        for eq_dir in ["EQX", "EQY"]:
            for sign in [1.0, -1.0]:
                combinations.append({
                    "id": f"UDCON{combo_id}",
                    "name": f"1.2(DL+LL{'+' if sign > 0 else '-'}{eq_dir})",
                    "factors": {"DL": 1.2, "LL": 1.2, eq_dir: 1.2 * sign},
                    "type": "Strength",
                    "code_ref": "IS 456 Table 18"
                })
                combo_id += 1
        
        for eq_dir in ["EQX", "EQY"]:
            for sign in [1.0, -1.0]:
                combinations.append({
                    "id": f"UDCON{combo_id}",
                    "name": f"1.5(DL{'+' if sign > 0 else '-'}{eq_dir})",
                    "factors": {"DL": 1.5, eq_dir: 1.5 * sign},
                    "type": "Strength",
                    "code_ref": "IS 456 Table 18"
                })
                combo_id += 1
        
        for eq_dir in ["EQX", "EQY"]:
            for sign in [1.0, -1.0]:
                combinations.append({
                    "id": f"UDCON{combo_id}",
                    "name": f"0.9DL{'+' if sign > 0 else '-'}1.5{eq_dir} (Uplift)",
                    "factors": {"DL": 0.9, eq_dir: 1.5 * sign},
                    "type": "Stability",
                    "is_critical": True,
                    "code_ref": "IS 456 Table 18 - Critical uplift case"
                })
                combo_id += 1
        
        if self.include_wind:
            for wl_dir in ["WLX", "WLY"]:
                combinations.append({
                    "id": f"UDCON{combo_id}",
                    "name": f"1.2(DL+LL+{wl_dir})",
                    "factors": {"DL": 1.2, "LL": 1.2, wl_dir: 1.2},
                    "type": "Strength",
                    "code_ref": "IS 456 Table 18"
                })
                combo_id += 1
            
            for wl_dir in ["WLX", "WLY"]:
                for sign in [1.0, -1.0]:
                    combinations.append({
                        "id": f"UDCON{combo_id}",
                        "name": f"0.9DL{'+' if sign > 0 else '-'}1.5{wl_dir} (Uplift)",
                        "factors": {"DL": 0.9, wl_dir: 1.5 * sign},
                        "type": "Stability",
                        "is_critical": True,
                        "code_ref": "IS 456 Table 18 - Wind uplift"
                    })
                    combo_id += 1
        
        if self.include_vertical_seismic:
            combinations.append({
                "id": f"UDCON{combo_id}",
                "name": "1.2(DL+LL+EQX+EQZ)",
                "factors": {"DL": 1.2, "LL": 1.2, "EQX": 1.2, "EQZ": 1.2},
                "type": "Strength",
                "code_ref": "IS 1893 - Vertical seismic"
            })
            combo_id += 1
        
        combinations.append({
            "id": f"UDCON{combo_id}",
            "name": "1.0(DL+LL)",
            "factors": {"DL": 1.0, "LL": 1.0},
            "type": "Serviceability",
            "code_ref": "IS 456 - Deflection check"
        })
        
        logger.info(f"Generated {len(combinations)} load combinations "
                   f"(including {sum(1 for c in combinations if c.get('is_critical'))} critical uplift cases)")
        
        return combinations
    
    def generate(self) -> AnalysisConfig:
        logger.info("Generating analysis configuration")
        
        seismic_params = self._configure_seismic_parameters()
        stiffness = self._configure_stiffness_modifiers()
        p_delta = self._configure_p_delta()
        seismic_mass = self._configure_seismic_mass()
        diaphragm = self._determine_diaphragm_type()
        load_combos = self._generate_load_combinations()
        
        total_seismic_weight = sum(fm.seismic_mass_kn for fm in self.floor_masses)
        
        config = AnalysisConfig(
            seismic_params=seismic_params,
            stiffness_modifiers=stiffness,
            p_delta=p_delta,
            seismic_mass=seismic_mass,
            diaphragm_type=diaphragm,
            load_combinations=load_combos,
            floor_masses=self.floor_masses,
            total_seismic_weight_kn=total_seismic_weight,
            warnings=self.warnings
        )
        
        logger.info(f"Analysis configuration complete: "
                   f"{len(load_combos)} combinations, "
                   f"seismic weight {total_seismic_weight:.0f}kN")
        
        return config


def calculate_base_shear(
    seismic_weight_kn: float,
    zone_factor: float,
    importance_factor: float,
    response_reduction: float,
    sa_g: float = 2.5
) -> float:
    ah = (zone_factor * importance_factor * sa_g) / (2 * response_reduction)
    base_shear = ah * seismic_weight_kn
    
    return base_shear
