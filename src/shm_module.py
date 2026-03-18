"""
Structural Health Monitoring (SHM) Module

Plans sensor deployment for Digital Twin integration and establishes baseline.
- Sensor Planning: Accelerometers, Strain Gauges, Tiltmeters
- Baseline Creation: Store As-Designed Stiffness/Frequency
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SensorLocation:
    sensor_id: str
    sensor_type: str  # Accelerometer, Strain Gauge, Tiltmeter
    location: str
    node_id: str
    axis: str  # X, Y, Z, or Omni
    purpose: str


@dataclass
class BaselineState:
    fundamental_frequency_hz: float
    stiffness_k_kn_m: float
    max_drift_ratio: float
    damping_ratio: float = 0.05
    timestamp: str = ""


class SHMPlanner:
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.sensors: List[SensorLocation] = []
        self.baseline: Optional[BaselineState] = None

    def plan_sensor_deployment(self, roof_node_id: str, critical_plastic_hinges: List[str]):
        """
        Identify optimal sensor locations based on FEM results/heuristics.
        """
        # 1. Accelerometer at Roof (Geometric Center)
        self.sensors.append(SensorLocation(
            sensor_id="ACC_01",
            sensor_type="Accelerometer",
            location="Roof Center",
            node_id=roof_node_id,
            axis="Omni",
            purpose="Measure Fundamental Period (T) and Mode Shapes"
        ))
        
        # 2. Strain Gauges at Plastic Hinges (Beam Ends / Col Bases)
        for i, node in enumerate(critical_plastic_hinges[:3]): # Limit to top 3 for demo
            self.sensors.append(SensorLocation(
                sensor_id=f"STR_{i+1:02d}",
                sensor_type="Strain Gauge",
                location="Critical Joint/Hinge",
                node_id=node,
                axis="X",
                purpose="Monitor Curvature/Rotation at Hinge Zone"
            ))
            
        # 3. Tiltmeter at Foundation
        self.sensors.append(SensorLocation(
            sensor_id="TILT_01",
            sensor_type="Tiltmeter",
            location="Foundation/Base",
            node_id="Base_Node",
            axis="Z",
            purpose="Monitor Differential Settlement"
        ))
        
        logger.info(f"Planned {len(self.sensors)} sensors for SHM.")

    def create_baseline(
        self, 
        freq_hz: float, 
        stiffness: float, 
        drift_ratio: float
    ) -> BaselineState:
        """
        Store As-Designed parameters as the 'Healthy State' baseline.
        """
        from datetime import datetime
        self.baseline = BaselineState(
            fundamental_frequency_hz=freq_hz,
            stiffness_k_kn_m=stiffness,
            max_drift_ratio=drift_ratio,
            timestamp=datetime.now().isoformat()
        )
        return self.baseline

    def check_anomaly(self, current_freq_hz: float) -> str:
        """
        Compare current frequency with baseline.
        If freq drops > 5%, implies stiffness degradation (Damage).
        """
        if not self.baseline:
            return "No Baseline"
            
        baseline_freq = self.baseline.fundamental_frequency_hz
        pct_change = ((current_freq_hz - baseline_freq) / baseline_freq) * 100
        
        if pct_change < -5.0:
            return f"WARNING: Stiffness Degradation detected! Freq dropped by {abs(pct_change):.2f}%"
        elif pct_change > 5.0:
            return f"Anomaly: Freq increased by {pct_change:.2f}% (Check mass reduction?)"
        
        return "Normal"

    def to_json(self) -> str:
        return json.dumps({
            "project": self.project_name,
            "baseline": self.baseline.__dict__ if self.baseline else None,
            "sensors": [s.__dict__ for s in self.sensors]
        }, indent=2)
