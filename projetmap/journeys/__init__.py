"""User Journey Detection — Discover traceable paths through an application triggered by user actions."""

from projetmap.journeys.detector import JourneyDetector
from projetmap.journeys.models import Journey, JourneyReport, JourneyStep, StepType

__all__ = ["JourneyDetector", "Journey", "JourneyReport", "JourneyStep", "StepType"]


def detect_journeys(graph_data: dict) -> JourneyReport:
    """Detect all user journeys from graph data.

    Args:
        graph_data: The full graph data dict from GraphBuilder.to_dict().

    Returns:
        JourneyReport with all discovered journeys.
    """
    detector = JourneyDetector()
    return detector.detect(graph_data)
