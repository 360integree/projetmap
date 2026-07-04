"""Interactive HTML exporter for user journeys using vis.js with hierarchical layout."""

import json
from pathlib import Path

from projetmap.journeys.models import JourneyReport


def _esc(s: str) -> str:
    """Escape ID for vis.js compatibility."""
    return s.replace("/", "_").replace(".", "_").replace("-", "_").replace(" ", "_")


# Step type color mapping
STEP_COLORS = {
    "ui_entry": {"bg": "#238636", "border": "#2ea043"},
    "ui_event": {"bg": "#1f6feb", "border": "#388bfd"},
    "handler": {"bg": "#8957e5", "border": "#a371f7"},
    "service_call": {"bg": "#30363d", "border": "#484f58"},
    "data_operation": {"bg": "#f0883e", "border": "#db6d28"},
    "api_call": {"bg": "#f778ba", "border": "#db61a2"},
    "state_update": {"bg": "#da3633", "border": "#f85149"},
    "navigation": {"bg": "#58a6ff", "border": "#79c0ff"},
}


def export_journeys_html(report: JourneyReport, output_path: Path) -> Path:
    """Export journey report as interactive HTML with vis.js hierarchical layout.

    All journeys are overlaid on one graph, color-coded by step type.
    Users can filter by step type, search by name, and click steps for details.

    Args:
        report: The JourneyReport to export.
        output_path: Path to write the HTML file.

    Returns:
        The output path.
    """
    project_name = "Project"

    # Build vis.js nodes and edges
    nodes = []
    edges = []
    step_info = {}  # node_id -> step detail dict
    journey_of = {}  # node_id -> journey name

    for journey in report.journeys:
        for i, step in enumerate(journey.steps):
            node_id = f"{_esc(journey.id)}__{step.id}"
            journey_of[node_id] = journey.name

            color = STEP_COLORS.get(step.step_type.value, STEP_COLORS["service_call"])
            nodes.append({
                "id": node_id,
                "label": step.name[:25],
                "group": step.step_type.value,
                "color": {
                    "background": color["bg"],
                    "border": color["border"],
                    "highlight": {"background": "#fff", "border": color["border"]},
                },
                "shape": "box",
                "font": {"size": 11, "color": "#c9d1d9", "strokeWidth": 2, "strokeColor": "#0d1117"},
                " borderWidth": 2,
                "title": (
                    f"{step.name}\n"
                    f"Type: {step.step_type.value}\n"
                    f"File: {step.file}:{step.line}\n"
                    f"Confidence: {step.confidence:.0%}\n"
                    f"Journey: {journey.name}"
                ),
                "level": i,
                "stepType": step.step_type.value,
            })

            step_info[node_id] = {
                "name": step.name,
                "type": step.step_type.value,
                "file": step.file,
                "line": step.line,
                "confidence": step.confidence,
                "journey": journey.name,
                "feature": journey.feature,
            }

            if i > 0:
                prev = journey.steps[i - 1]
                prev_id = f"{_esc(journey.id)}__{prev.id}"
                edges.append({
                    "from": prev_id,
                    "to": node_id,
                    "label": prev.step_type.value,
                    "color": {"color": "#30363d", "highlight": "#58a6ff"},
                    "arrows": {"to": {"enabled": True, "scaleFactor": 0.4}},
                    "smooth": {"type": "curvedCW", "roundness": 0.15},
                })

    # Journey summary for sidebar
    journey_list = []
    for j in report.journeys:
        journey_list.append({
            "id": j.id,
            "name": j.name,
            "feature": j.feature,
            "confidence": j.confidence,
            "stepCount": len(j.steps),
        })

    # Summary stats
    summary = report.to_dict()["summary"]
    total_journeys = summary.get("total_journeys", 0)
    feature_count = len(summary.get("by_feature", {}))

    vis_js_path = Path("/tmp/vis-network.min.js")
    vis_js = vis_js_path.read_text() if vis_js_path.exists() else "// vis.js not found"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>User Journeys — {project_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; overflow: hidden; display: flex; height: 100vh; }}

/* Sidebar */
#sidebar {{ width: 280px; min-width: 280px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; overflow: hidden; }}
#sidebar-header {{ padding: 12px 16px; border-bottom: 1px solid #30363d; }}
#sidebar-header h2 {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
#sidebar-header .stats {{ font-size: 11px; color: #8b949e; }}
#search {{ width: 100%; background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 10px; border-radius: 4px; font-size: 12px; margin-top: 8px; }}
#filters {{ padding: 8px 16px; border-bottom: 1px solid #30363d; }}
#filters label {{ display: flex; align-items: center; gap: 6px; font-size: 11px; cursor: pointer; padding: 2px 0; }}
#filters input[type="checkbox"] {{ accent-color: #58a6ff; }}
#journey-list {{ flex: 1; overflow-y: auto; padding: 8px 0; }}
.journey-item {{ padding: 8px 16px; cursor: pointer; border-bottom: 1px solid #21262d; font-size: 12px; }}
.journey-item:hover {{ background: #21262d; }}
.journey-item.active {{ background: #1f6feb22; border-left: 3px solid #58a6ff; }}
.journey-item .jname {{ font-weight: 500; margin-bottom: 2px; }}
.journey-item .jmeta {{ font-size: 10px; color: #8b949e; }}
.journey-item .jconf {{ color: #3fb950; font-size: 10px; }}

/* Main area */
#main {{ flex: 1; display: flex; flex-direction: column; }}
#header {{ padding: 10px 20px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }}
#header h1 {{ font-size: 15px; font-weight: 600; }}
#controls {{ padding: 8px 20px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; gap: 8px; align-items: center; }}
#controls button {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
#controls button:hover {{ background: #30363d; }}
#graph {{ flex: 1; }}

/* Legend */
#legend {{ position: absolute; bottom: 12px; left: 300px; background: #161b22ee; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px; font-size: 10px; z-index: 10; }}
#legend .item {{ display: flex; align-items: center; gap: 6px; margin: 2px 0; }}
#legend .dot {{ width: 8px; height: 8px; border-radius: 50%; }}

/* Info panel */
#info {{ position: absolute; top: 80px; right: 12px; background: #161b22ee; border: 1px solid #30363d; border-radius: 6px; padding: 12px; width: 300px; max-height: 400px; overflow-y: auto; display: none; font-size: 11px; z-index: 10; }}
#info h3 {{ margin-bottom: 6px; font-size: 12px; color: #fff; word-break: break-all; }}
#info .meta {{ color: #8b949e; margin-bottom: 6px; }}
#info .rel {{ padding: 2px 0; color: #8b949e; border-bottom: 1px solid #21262d; }}
#info .rel-type {{ color: #58a6ff; }}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-header">
    <h2>User Journeys</h2>
    <div class="stats">{total_journeys} journeys · {feature_count} features</div>
    <input type="text" id="search" placeholder="Search journeys...">
  </div>
  <div id="filters"></div>
  <div id="journey-list"></div>
</div>

<div id="main">
  <div id="header">
    <h1>User Journeys</h1>
  </div>
  <div id="controls">
    <button onclick="showAll()">Show All</button>
    <button onclick="network.fit()">Fit</button>
  </div>
  <div id="graph"></div>
</div>

<div id="legend"></div>
<div id="info">
  <h3 id="info-title"></h3>
  <div class="meta" id="info-meta"></div>
  <div id="info-body"></div>
</div>

<script>
{vis_js}
</script>
<script>
const allNodes = {json.dumps(nodes)};
const allEdges = {json.dumps(edges)};
const stepInfo = {json.dumps(step_info)};
const journeyOf = {json.dumps(journey_of)};
const journeyList = {json.dumps(journey_list)};
const stepColors = {json.dumps({k: v["bg"] for k, v in STEP_COLORS.items()})};

const container = document.getElementById('graph');
let network, nodeDataSet, edgeDataSet;
let activeFilters = new Set(Object.keys(stepColors));
let activeJourney = null;

// Initialize journey list sidebar
function renderJourneyList(filter = '') {{
  const list = document.getElementById('journey-list');
  const q = filter.toLowerCase();
  const filtered = journeyList.filter(j =>
    !q || j.name.toLowerCase().includes(q) || j.feature.toLowerCase().includes(q)
  );
  list.innerHTML = filtered.map(j =>
    '<div class="journey-item' + (activeJourney === j.id ? ' active' : '') +
    '" onclick="selectJourney(\\'' + j.id + '\\')">' +
    '<div class="jname">' + j.name + '</div>' +
    '<div class="jmeta">' + j.feature + ' · ' + j.stepCount + ' steps</div>' +
    '<div class="jconf">' + (j.confidence * 100).toFixed(0) + '% confidence</div>' +
    '</div>'
  ).join('');
}}

// Initialize filter checkboxes
function renderFilters() {{
  const filters = document.getElementById('filters');
  const types = Object.keys(stepColors);
  filters.innerHTML = '<div style="font-size:11px;color:#8b949e;margin-bottom:4px">Filter by step type:</div>' +
    types.map(t =>
      '<label><input type="checkbox" checked onchange="toggleFilter(\\'' + t + '\\')">' +
      '<div class="dot" style="background:' + stepColors[t] + ';width:8px;height:8px;border-radius:50%;display:inline-block"></div> ' +
      t.replace('_', ' ') + '</label>'
    ).join('');
}}

function toggleFilter(type) {{
  if (activeFilters.has(type)) activeFilters.delete(type);
  else activeFilters.add(type);
  applyFilters();
}}

function applyFilters() {{
  if (!nodeDataSet) return;
  nodeDataSet.forEach(n => {{
    const visible = activeFilters.has(n.stepType) && (!activeJourney || journeyOf[n.id] === activeJourney);
    nodeDataSet.update({{ id: n.id, hidden: !visible }});
  }});
}}

function selectJourney(journeyId) {{
  activeJourney = activeJourney === journeyId ? null : journeyId;
  renderJourneyList(document.getElementById('search').value);
  applyFilters();
  if (activeJourney && network) {{
    // Fit to the visible nodes
    const visibleIds = allNodes
      .filter(n => journeyOf[n.id] === activeJourney)
      .map(n => n.id);
    if (visibleIds.length > 0) {{
      network.fit({{ nodes: visibleIds, animation: true }});
    }}
  }}
}}

function showAll() {{
  activeJourney = null;
  renderJourneyList(document.getElementById('search').value);
  activeFilters = new Set(Object.keys(stepColors));
  renderFilters();
  applyFilters();
  if (network) network.fit();
}}

// Build vis.js graph
function initGraph() {{
  const visibleNodes = allNodes.filter(n => activeFilters.has(n.stepType));
  const nodeIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = allEdges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));

  nodeDataSet = new vis.DataSet(visibleNodes.map(n => ({{
    id: n.id,
    label: n.label,
    color: n.color,
    shape: n.shape,
    font: n.font,
    borderWidth: n.borderWidth || 2,
    title: n.title,
    level: n.level,
    stepType: n.stepType,
    hidden: false,
  }})));

  edgeDataSet = new vis.DataSet(visibleEdges.map(e => ({{
    from: e.from,
    to: e.to,
    label: e.label || '',
    color: e.color,
    arrows: e.arrows,
    smooth: e.smooth,
    font: {{ size: 8, color: '#58a6ff', strokeWidth: 0 }},
  }})));

  network = new vis.Network(container, {{ nodes: nodeDataSet, edges: edgeDataSet }}, {{
    layout: {{
      hierarchical: {{
        direction: 'UD',
        sortMethod: 'directed',
        levelSeparation: 120,
        nodeSpacing: 100,
        treeSpacing: 150,
      }}
    }},
    physics: {{ enabled: false }},
    interaction: {{ hover: true, tooltipDelay: 80, zoomView: true, dragView: true }},
  }});

  window.network = network;

  network.on('click', function(p) {{
    if (p.nodes.length > 0) showStepInfo(p.nodes[0]);
    else document.getElementById('info').style.display = 'none';
  }});
}}

function showStepInfo(nodeId) {{
  const info = stepInfo[nodeId];
  if (!info) return;

  document.getElementById('info-title').textContent = info.name;
  document.getElementById('info-meta').innerHTML =
    '<div><b>Type:</b> ' + info.type + '</div>' +
    '<div><b>File:</b> ' + info.file + ':' + info.line + '</div>' +
    '<div><b>Confidence:</b> ' + (info.confidence * 100).toFixed(0) + '%</div>' +
    '<div><b>Journey:</b> ' + info.journey + '</div>' +
    '<div><b>Feature:</b> ' + info.feature + '</div>';

  // Show related steps in same journey
  const relatedSteps = allNodes.filter(n => journeyOf[n.id] === info.journey);
  let body = '<div style="margin-top:8px"><b>Journey Steps (' + relatedSteps.length + '):</b></div>';
  relatedSteps.forEach(s => {{
    const si = stepInfo[s.id];
    if (si) {{
      body += '<div class="rel"><span class="rel-type">' + si.type + '</span> ' + si.name + '</div>';
    }}
  }});

  document.getElementById('info-body').innerHTML = body;
  document.getElementById('info').style.display = 'block';
}}

// Legend
function renderLegend() {{
  const legend = document.getElementById('legend');
  const items = Object.entries(stepColors).map(([type, color]) =>
    '<div class="item"><div class="dot" style="background:' + color + '"></div> ' + type.replace('_', ' ') + '</div>'
  ).join('');
  legend.innerHTML = items;
}}

// Search
let searchTimeout;
document.getElementById('search').addEventListener('input', function(e) {{
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {{
    renderJourneyList(e.target.value);
  }}, 150);
}});

// Init
renderFilters();
renderJourneyList();
renderLegend();
initGraph();
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
