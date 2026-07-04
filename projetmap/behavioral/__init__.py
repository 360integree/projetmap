"""Behavioral analysis: call graphs, state flow, dead code detection."""
from typing import Dict

from projetmap.behavioral.call_graph import analyze_call_graph
from projetmap.behavioral.state_flow import analyze_state_flow


def run_behavioral_analysis(graph_data: dict, behavioral_json_path: str) -> dict:
    """Run all behavioral analyzers on extracted behavioral data."""
    import json

    with open(behavioral_json_path) as f:
        data = json.load(f)

    results = {}

    # Call graph analysis (graph_data param reserved for future cross-reference)
    cg_results = analyze_call_graph(data, {})
    results.update(cg_results)

    # State flow analysis
    sf_results = analyze_state_flow(data)
    results.update(sf_results)

    # Summary
    state_mutations = data.get('state_mutations', [])
    unpaired = results.get('unpaired_listeners', [])

    results['summary'] = {
        'files_analyzed': data.get('file_count', 0),
        'dead_functions': len(results.get('dead_code', [])),
        'hot_paths': len(results.get('hot_paths', [])),
        'total_state_mutations': len(state_mutations),
        'unpaired_listeners': len([
            u for u in unpaired
            if u.get('unpaired', 0) > 0
        ]),
    }

    return results
