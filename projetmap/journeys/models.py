"""Data models for user journey detection."""

from dataclasses import dataclass, field
from enum import Enum


class StepType(str, Enum):
    """Classification of a journey step."""

    UI_ENTRY = "ui_entry"
    UI_EVENT = "ui_event"
    HANDLER = "handler"
    SERVICE_CALL = "service_call"
    DATA_OPERATION = "data_operation"
    API_CALL = "api_call"
    STATE_UPDATE = "state_update"
    NAVIGATION = "navigation"


@dataclass
class JourneyStep:
    """A single step in a user journey."""

    id: str
    node_id: str
    step_type: StepType
    name: str
    file: str
    line: int
    confidence: float = 1.0
    description: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Journey:
    """A complete user journey through the application."""

    id: str
    name: str
    feature: str
    steps: list[JourneyStep] = field(default_factory=list)
    entry_point: str = ""
    confidence: float = 0.0
    step_types_present: list[StepType] = field(default_factory=list)
    file: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class JourneyReport:
    """Complete report of all discovered journeys."""

    journeys: list[Journey] = field(default_factory=list)
    total_journeys: int = 0
    by_feature: dict[str, int] = field(default_factory=dict)
    by_step_type: dict[str, int] = field(default_factory=dict)
    confidence_distribution: dict[str, int] = field(default_factory=dict)
    files_analyzed: int = 0

    def to_dict(self) -> dict:
        return {
            "journeys": [
                {
                    "id": j.id,
                    "name": j.name,
                    "feature": j.feature,
                    "confidence": j.confidence,
                    "entry_point": j.entry_point,
                    "file": j.file,
                    "step_count": len(j.steps),
                    "steps": [
                        {
                            "id": s.id,
                            "node_id": s.node_id,
                            "step_type": s.step_type.value,
                            "name": s.name,
                            "file": s.file,
                            "line": s.line,
                            "description": s.description,
                            "confidence": s.confidence,
                        }
                        for s in j.steps
                    ],
                }
                for j in self.journeys
            ],
            "summary": {
                "total_journeys": self.total_journeys,
                "by_feature": self.by_feature,
                "by_step_type": self.by_step_type,
                "confidence_distribution": self.confidence_distribution,
                "files_analyzed": self.files_analyzed,
            },
        }
