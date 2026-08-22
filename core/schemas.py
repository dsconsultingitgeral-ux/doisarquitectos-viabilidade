from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class SourceRef(BaseModel):
    title: str = ""
    url: str = ""
    publisher: str = ""
    date: str = ""
    article: str = ""
    page: str = ""
    quote_or_basis: str = ""
    source_type: str = "web"

class Finding(BaseModel):
    label: str
    value: str = ""
    status: str = "a_confirmar"  # confirmado, calculado, interpretacao, a_confirmar, conflito
    confidence: int = 0
    rationale: str = ""
    sources: List[SourceRef] = Field(default_factory=list)

class DocumentRecord(BaseModel):
    filename: str
    document_type: str = "outro"
    importance: str = "complementar"
    detected_pages: Dict[str, List[int]] = Field(default_factory=dict)
    extracted: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

class StudyState(BaseModel):
    study_ref: str = ""
    client_name: str = ""
    location_text: str = ""
    municipality: str = ""
    parish: str = ""
    district: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    polygon_geojson: Optional[Dict[str, Any]] = None
    estimated_area_m2: Optional[float] = None
    objective: str = "Determinar o melhor aproveitamento admissível"
    priority: str = "Equilíbrio entre aproveitamento e risco"
    documents: List[DocumentRecord] = Field(default_factory=list)
    document_findings: Dict[str, Any] = Field(default_factory=dict)
    web_research: Dict[str, Any] = Field(default_factory=dict)
    rules: Dict[str, Any] = Field(default_factory=dict)
    calculations: Dict[str, Any] = Field(default_factory=dict)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    audit: Dict[str, Any] = Field(default_factory=dict)
