from typing import List, Optional
from pydantic import BaseModel
from .calculations import ComponentLoad, AggregatedLoad, BeamAnalysisResult, ColumnCheckResult
from .materials import Material
from .sections import SectionProperties

class BeamReportItem(BaseModel):
    id: str
    description: str
    span_mm: float
    loads: AggregatedLoad
    analysis_result: BeamAnalysisResult
    section_properties: SectionProperties

class ColumnReportItem(BaseModel):
    id: str
    description: str
    height_mm: float
    loads: AggregatedLoad
    check_result: ColumnCheckResult
    section_properties: SectionProperties

class ProjectReport(BaseModel):
    project_name: str
    engineer: str
    date: str
    beams: List[BeamReportItem] = []
    columns: List[ColumnReportItem] = []
    materials_used: List[str] = []
