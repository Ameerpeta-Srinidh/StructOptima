"""
BIM Interoperability Module - COBie v3 Export

Generates COBie (Construction Operations Building Information Exchange) data
for Facility Management integration.

Tables generated:
- Type: Component types (Beam, Column, Slab)
- Component: Individual instances with unique IDs
- Attribute: Design metadata (Fire rating, Load capacity)
- Coordinate: X, Y, Z for site layout
"""

import csv
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CobieType:
    name: str
    category: str
    description: str
    asset_type: str = "Fixed"
    manufacturer: str = "N/A"
    model_number: str = "N/A"
    warrantry_guarantor_parts: str = "N/A"
    warranty_duration_parts: float = 0.0


@dataclass
class CobieComponent:
    name: str
    type_name: str
    space_name: str
    description: str
    serial_number: str = "N/A"
    installation_date: str = ""
    warranty_start_date: str = ""


@dataclass
class CobieAttribute:
    name: str
    category: str
    description: str
    value: str
    unit: str
    allowed_values: str = ""


@dataclass
class CobieCoordinate:
    name: str
    category: str
    description: str
    coordinate_x: float
    coordinate_y: float
    coordinate_z: float
    clockwise_rotation: float = 0.0
    elevational_rotation: float = 0.0
    yaw_rotation: float = 0.0


class CobieExporter:
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.types: List[CobieType] = []
        self.components: List[CobieComponent] = []
        self.attributes: List[CobieAttribute] = []
        self.coordinates: List[CobieCoordinate] = []
        self.created_on = datetime.now().isoformat()

    def add_type(self, name: str, category: str, description: str):
        """Register a component type (e.g., 'C1_Column')."""
        self.types.append(CobieType(name, category, description))

    def add_component(self, name: str, type_name: str, space: str, description: str):
        """Register a component instance (e.g., 'C1_Ground_01')."""
        self.components.append(CobieComponent(name, type_name, space, description))

    def add_attribute(self, row_name: str, category: str, value: str, unit: str = ""):
        """Add metadata to a component (e.g., FireRating=2hr)."""
        self.attributes.append(CobieAttribute(
            name=row_name,  # The component name this attaches to
            category=category,
            description="Design Attribute",
            value=str(value),
            unit=unit
        ))

    def add_coordinate(self, name: str, x: float, y: float, z: float):
        """Add X,Y,Z coordinates for site layout."""
        self.coordinates.append(CobieCoordinate(
            name=name,
            category="Design",
            description="Centroid",
            coordinate_x=x,
            coordinate_y=y,
            coordinate_z=z
        ))

    def export_json(self) -> str:
        """Export full COBie dataset as JSON."""
        data = {
            "cobie_version": "3.0",
            "project": self.project_name,
            "created_on": self.created_on,
            "types": [t.__dict__ for t in self.types],
            "components": [c.__dict__ for c in self.components],
            "attributes": [a.__dict__ for a in self.attributes],
            "coordinates": [c.__dict__ for c in self.coordinates]
        }
        return json.dumps(data, indent=2)

    def export_csv(self, base_filename: str):
        """Export separate CSVs for each COBie table."""
        # Type Table
        with open(f"{base_filename}_Type.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CobieType.__annotations__.keys())
            w.writeheader()
            w.writerows([t.__dict__ for t in self.types])
            
        # Component Table
        with open(f"{base_filename}_Component.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CobieComponent.__annotations__.keys())
            w.writeheader()
            w.writerows([c.__dict__ for c in self.components])

        # Attribute Table
        with open(f"{base_filename}_Attribute.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CobieAttribute.__annotations__.keys())
            w.writeheader()
            w.writerows([a.__dict__ for a in self.attributes])

        # Coordinate Table
        with open(f"{base_filename}_Coordinate.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CobieCoordinate.__annotations__.keys())
            w.writeheader()
            w.writerows([c.__dict__ for c in self.coordinates])
