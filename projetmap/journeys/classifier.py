"""Step classifier — assigns StepType to graph nodes based on name, type, and context."""

import re

from projetmap.journeys.models import StepType

# Compiled patterns for classification
_HANDLER_PATTERNS = [
    re.compile(r"^on[A-Z]\w*"),
    re.compile(r"^handle[A-Z]\w*"),
    re.compile(r"^_on[A-Z]\w*"),
    re.compile(r"^(tap|click|submit|press|change|input|scroll|swipe)\w*", re.I),
]

_STATE_UPDATE_NAMES = {
    "setstate",
    "notifylisteners",
    "emit",
    "update",
    "markneedsbuild",
    "setstateasync",
    "addlistener",
}

_NAVIGATION_PATTERNS = [
    re.compile(r"navigate|redirect|push|pop|replace|goto|route", re.I),
]

_DATA_OPERATION_PATTERNS = [
    re.compile(r"save|create|update|delete|find|query|fetch|load|store|insert", re.I),
]

_DATA_FILE_PATTERNS = [
    re.compile(r"repository|dao|model|table|database|db|drift|supabase|firebase", re.I),
]

_API_PATTERNS = [
    re.compile(r"api|http|request|fetch|dio|axios|client", re.I),
]

_SERVICE_PATTERNS = [
    re.compile(r"service|usecase|interactor|controller|manager|provider", re.I),
]

_SCREEN_PATTERNS = [
    re.compile(r"screen|page|view|widget|component", re.I),
]


def classify_step(node_id: str, entity: dict, outgoing_edge_types: set[str]) -> StepType:
    """Classify a graph node into a journey step type.

    Args:
        node_id: The graph node ID.
        entity: Entity dict with 'name', 'type', 'file' keys.
        outgoing_edge_types: Set of relationship types for outgoing edges from this node.

    Returns:
        The most likely StepType for this node.
    """
    name = entity.get("name", "").lower()
    name_raw = entity.get("name", "")
    entity_type = entity.get("type", "")
    file_path = entity.get("file", "").lower()

    # UI entry: route entity or Screen/Page/View naming
    if entity_type == "route":
        return StepType.UI_ENTRY
    if _SCREEN_PATTERNS[0].search(name):
        return StepType.UI_ENTRY

    # Event handler (test against original name for camelCase patterns)
    for pattern in _HANDLER_PATTERNS:
        if pattern.search(name_raw) or pattern.search(name):
            return StepType.HANDLER

    # State update
    if name in _STATE_UPDATE_NAMES:
        return StepType.STATE_UPDATE
    if re.search(r"set\s*state|notify\s*listeners|\.emit\(", name):
        return StepType.STATE_UPDATE

    # Navigation
    for pattern in _NAVIGATION_PATTERNS:
        if pattern.search(name):
            return StepType.NAVIGATION
    if "routes_to" in outgoing_edge_types:
        return StepType.NAVIGATION

    # Data operation
    for pattern in _DATA_OPERATION_PATTERNS:
        if pattern.search(name):
            for fp in _DATA_FILE_PATTERNS:
                if fp.search(file_path):
                    return StepType.DATA_OPERATION

    # API call
    for pattern in _API_PATTERNS:
        if pattern.search(name):
            return StepType.API_CALL

    # Service call (default for business logic with outgoing calls)
    for pattern in _SERVICE_PATTERNS:
        if pattern.search(name):
            return StepType.SERVICE_CALL

    # Default: service call for anything with outgoing edges
    if "calls" in outgoing_edge_types:
        return StepType.SERVICE_CALL

    return StepType.SERVICE_CALL
