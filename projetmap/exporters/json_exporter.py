"""Export graph to JSON format."""

import json
from pathlib import Path


def export_json(graph_data: dict, output_path: Path) -> Path:
    """Export graph data to graph.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(graph_data, f, indent=2)
    return output_path
