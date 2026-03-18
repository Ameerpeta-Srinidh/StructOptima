"""
Quantity Takeoff Module - IS 1200 Compliant

Calculates Bill of Quantities (BOQ) for RCC structures:
- Concrete volumes
- Shuttering/Formwork areas
- Steel quantities (from BBS)
- Cost estimation with DSR rates
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import math

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConcreteQuantity:
    element_id: str
    element_type: str
    length_m: float
    width_m: float
    depth_m: float
    volume_m3: float
    grade: str = "M25"


@dataclass
class ShutteringQuantity:
    element_id: str
    element_type: str
    area_m2: float
    type: str = "Plywood"


@dataclass
class SteelQuantity:
    diameter_mm: int
    weight_kg: float
    length_m: float = 0.0


@dataclass
class BOQSummary:
    concrete_m3: float = 0.0
    shuttering_m2: float = 0.0
    steel_kg: float = 0.0
    concrete_by_grade: Dict[str, float] = field(default_factory=dict)
    steel_by_dia: Dict[int, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "concrete_m3": round(self.concrete_m3, 2),
            "shuttering_m2": round(self.shuttering_m2, 2),
            "steel_kg": round(self.steel_kg, 2),
            "steel_tonnes": round(self.steel_kg / 1000, 3),
            "by_grade": {k: round(v, 2) for k, v in self.concrete_by_grade.items()},
            "steel_by_diameter": {k: round(v, 2) for k, v in self.steel_by_dia.items()}
        }


@dataclass
class CostEstimate:
    concrete_cost: float = 0.0
    steel_cost: float = 0.0
    shuttering_cost: float = 0.0
    labour_cost: float = 0.0
    total_cost: float = 0.0
    cost_per_sqft: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "concrete": round(self.concrete_cost, 0),
            "steel": round(self.steel_cost, 0),
            "shuttering": round(self.shuttering_cost, 0),
            "labour": round(self.labour_cost, 0),
            "total": round(self.total_cost, 0),
            "per_sqft": round(self.cost_per_sqft, 0)
        }


DSR_RATES_DEFAULT = {
    "concrete_M20": 5500.0,
    "concrete_M25": 6000.0,
    "concrete_M30": 6500.0,
    "steel_Fe415": 65.0,
    "steel_Fe500": 68.0,
    "shuttering_plywood": 450.0,
    "shuttering_steel": 350.0,
    "labour_percent": 15.0
}


class QuantityTakeoff:
    
    def __init__(
        self,
        concrete_grade: str = "M25",
        steel_grade: str = "Fe415",
        dsr_rates: Optional[Dict] = None
    ):
        self.concrete_grade = concrete_grade
        self.steel_grade = steel_grade
        self.dsr_rates = dsr_rates or DSR_RATES_DEFAULT
        
        self.concrete_items: List[ConcreteQuantity] = []
        self.shuttering_items: List[ShutteringQuantity] = []
        self.steel_items: List[SteelQuantity] = []
        
        logger.info(f"QuantityTakeoff initialized: {concrete_grade}, {steel_grade}")
    
    def add_beam(
        self,
        element_id: str,
        length_mm: float,
        width_mm: float,
        depth_mm: float,
        deduct_column_width_mm: float = 0.0
    ):
        length_m = (length_mm - deduct_column_width_mm) / 1000
        width_m = width_mm / 1000
        depth_m = depth_mm / 1000
        
        volume = length_m * width_m * depth_m
        
        self.concrete_items.append(ConcreteQuantity(
            element_id=element_id,
            element_type="Beam",
            length_m=length_m,
            width_m=width_m,
            depth_m=depth_m,
            volume_m3=volume,
            grade=self.concrete_grade
        ))
        
        shutter_area = 2 * length_m * depth_m + length_m * width_m
        
        self.shuttering_items.append(ShutteringQuantity(
            element_id=element_id,
            element_type="Beam",
            area_m2=shutter_area
        ))
        
        logger.info(f"Beam {element_id}: {volume:.3f}m³, {shutter_area:.2f}m² shuttering")
    
    def add_column(
        self,
        element_id: str,
        height_mm: float,
        width_mm: float,
        depth_mm: float,
        deduct_beam_depth_mm: float = 0.0
    ):
        height_m = (height_mm - deduct_beam_depth_mm) / 1000
        width_m = width_mm / 1000
        depth_m = depth_mm / 1000
        
        volume = height_m * width_m * depth_m
        
        self.concrete_items.append(ConcreteQuantity(
            element_id=element_id,
            element_type="Column",
            length_m=height_m,
            width_m=width_m,
            depth_m=depth_m,
            volume_m3=volume,
            grade=self.concrete_grade
        ))
        
        shutter_area = 2 * height_m * (width_m + depth_m)
        
        self.shuttering_items.append(ShutteringQuantity(
            element_id=element_id,
            element_type="Column",
            area_m2=shutter_area
        ))
        
        logger.info(f"Column {element_id}: {volume:.3f}m³, {shutter_area:.2f}m² shuttering")
    
    def add_slab(
        self,
        element_id: str,
        length_mm: float,
        width_mm: float,
        thickness_mm: float
    ):
        length_m = length_mm / 1000
        width_m = width_mm / 1000
        thickness_m = thickness_mm / 1000
        
        volume = length_m * width_m * thickness_m
        
        self.concrete_items.append(ConcreteQuantity(
            element_id=element_id,
            element_type="Slab",
            length_m=length_m,
            width_m=width_m,
            depth_m=thickness_m,
            volume_m3=volume,
            grade=self.concrete_grade
        ))
        
        shutter_area = length_m * width_m
        
        self.shuttering_items.append(ShutteringQuantity(
            element_id=element_id,
            element_type="Slab",
            area_m2=shutter_area
        ))
        
        logger.info(f"Slab {element_id}: {volume:.3f}m³, {shutter_area:.2f}m² shuttering")
    
    def add_footing(
        self,
        element_id: str,
        length_mm: float,
        width_mm: float,
        depth_mm: float
    ):
        length_m = length_mm / 1000
        width_m = width_mm / 1000
        depth_m = depth_mm / 1000
        
        volume = length_m * width_m * depth_m
        
        self.concrete_items.append(ConcreteQuantity(
            element_id=element_id,
            element_type="Footing",
            length_m=length_m,
            width_m=width_m,
            depth_m=depth_m,
            volume_m3=volume,
            grade=self.concrete_grade
        ))
        
        shutter_area = 2 * depth_m * (length_m + width_m)
        
        self.shuttering_items.append(ShutteringQuantity(
            element_id=element_id,
            element_type="Footing",
            area_m2=shutter_area
        ))
    
    def add_steel_from_bbs(self, bbs_summary: Dict[int, float]):
        for dia, weight in bbs_summary.items():
            self.steel_items.append(SteelQuantity(
                diameter_mm=dia,
                weight_kg=weight
            ))
    
    def get_summary(self) -> BOQSummary:
        summary = BOQSummary()
        
        for item in self.concrete_items:
            summary.concrete_m3 += item.volume_m3
            if item.grade not in summary.concrete_by_grade:
                summary.concrete_by_grade[item.grade] = 0.0
            summary.concrete_by_grade[item.grade] += item.volume_m3
        
        for item in self.shuttering_items:
            summary.shuttering_m2 += item.area_m2
        
        for item in self.steel_items:
            summary.steel_kg += item.weight_kg
            if item.diameter_mm not in summary.steel_by_dia:
                summary.steel_by_dia[item.diameter_mm] = 0.0
            summary.steel_by_dia[item.diameter_mm] += item.weight_kg
        
        return summary
    
    def estimate_cost(self, built_up_area_sqft: float = 0.0) -> CostEstimate:
        summary = self.get_summary()
        estimate = CostEstimate()
        
        concrete_rate = self.dsr_rates.get(f"concrete_{self.concrete_grade}", 6000.0)
        estimate.concrete_cost = summary.concrete_m3 * concrete_rate
        
        steel_rate = self.dsr_rates.get(f"steel_{self.steel_grade}", 65.0)
        estimate.steel_cost = summary.steel_kg * steel_rate
        
        shutter_rate = self.dsr_rates.get("shuttering_plywood", 450.0)
        estimate.shuttering_cost = summary.shuttering_m2 * shutter_rate
        
        material_cost = estimate.concrete_cost + estimate.steel_cost + estimate.shuttering_cost
        labour_percent = self.dsr_rates.get("labour_percent", 15.0)
        estimate.labour_cost = material_cost * labour_percent / 100
        
        estimate.total_cost = material_cost + estimate.labour_cost
        
        if built_up_area_sqft > 0:
            estimate.cost_per_sqft = estimate.total_cost / built_up_area_sqft
        
        logger.info(f"Cost estimate: Rs.{estimate.total_cost:,.0f}")
        return estimate
    
    def generate_boq_report(self, built_up_area_sqft: float = 0.0) -> str:
        summary = self.get_summary()
        cost = self.estimate_cost(built_up_area_sqft)
        
        lines = []
        lines.append("=" * 60)
        lines.append("BILL OF QUANTITIES (BOQ)")
        lines.append("=" * 60)
        lines.append("")
        
        lines.append("CONCRETE:")
        for grade, vol in summary.concrete_by_grade.items():
            lines.append(f"  {grade}: {vol:.2f} m³")
        lines.append(f"  TOTAL: {summary.concrete_m3:.2f} m³")
        lines.append("")
        
        lines.append("SHUTTERING:")
        lines.append(f"  Total Area: {summary.shuttering_m2:.2f} m²")
        lines.append("")
        
        lines.append("STEEL:")
        for dia in sorted(summary.steel_by_dia.keys()):
            wt = summary.steel_by_dia[dia]
            lines.append(f"  {dia}mm: {wt:.2f} kg")
        lines.append(f"  TOTAL: {summary.steel_kg:.2f} kg ({summary.steel_kg/1000:.3f} T)")
        lines.append("")
        
        lines.append("=" * 60)
        lines.append("COST ESTIMATE")
        lines.append("=" * 60)
        lines.append(f"  Concrete: Rs.{cost.concrete_cost:,.0f}")
        lines.append(f"  Steel: Rs.{cost.steel_cost:,.0f}")
        lines.append(f"  Shuttering: Rs.{cost.shuttering_cost:,.0f}")
        lines.append(f"  Labour (15%): Rs.{cost.labour_cost:,.0f}")
        lines.append("-" * 40)
        lines.append(f"  TOTAL: Rs.{cost.total_cost:,.0f}")
        if built_up_area_sqft > 0:
            lines.append(f"  Per Sqft: Rs.{cost.cost_per_sqft:,.0f}")
        
        return "\n".join(lines)
    
    def to_json(self, built_up_area_sqft: float = 0.0) -> str:
        summary = self.get_summary()
        cost = self.estimate_cost(built_up_area_sqft)
        
        return json.dumps({
            "BOQ": summary.to_dict(),
            "cost_estimate": cost.to_dict(),
            "currency": "INR"
        }, indent=2)


def calculate_steel_ratio(steel_kg: float, concrete_m3: float) -> float:
    if concrete_m3 <= 0:
        return 0.0
    return steel_kg / concrete_m3
