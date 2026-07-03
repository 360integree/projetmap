"""Export graph as interactive HTML using vis.js (full featured)."""

from pathlib import Path
from typing import Dict
import json


def _esc(s: str) -> str:
    return s.replace("/", "_").replace(".", "_").replace("-", "_").replace(" ", "_")


def export_html(graph_data: Dict, output_path: Path) -> Path:
    project = graph_data.get("project", {})
    stats = graph_data.get("metadata", {})
    title = f"{project.get('name', 'Project')} — Knowledge Graph"
    stats_text = (
        f"{stats.get('entity_count', 0)} entities · "
        f"{stats.get('relationship_count', 0)} relationships"
    )

    entities = graph_data.get("entities", [])
    relationships = graph_data.get("relationships", [])
    god_nodes = stats.get("god_nodes", [])

    # Build lookup structures
    god_ids = {_esc(g["id"]) for g in god_nodes}
    entity_map = {_esc(e["id"]): e for e in entities}

    # Group by type
    type_groups = {}
    for e in entities:
        t = e.get("type", "unknown")
        if t not in type_groups:
            type_groups[t] = []
        type_groups[t].append(e)

    # Build cluster nodes
    cluster_nodes = []
    for g in god_nodes:
        cluster_nodes.append({
            "id": _esc(g["id"]),
            "name": g["id"].split("/")[-1],
            "type": "god",
            "file": g["id"],
            "size": 22,
            "shape": "diamond",
            "cluster": None,
        })

    for t, ents in type_groups.items():
        if t in ("module", "config"):
            continue
        cid = f"cluster_{t}"
        cluster_nodes.append({
            "id": cid,
            "name": f"{t} ({len(ents)})",
            "type": "cluster",
            "entityType": t,
            "file": f"{len(ents)} entities",
            "size": 14 + min(len(ents) // 20, 12),
            "shape": "dot",
            "cluster": None,
        })

    # Map entities to clusters
    ent_to_cluster = {}
    for e in entities:
        eid = _esc(e["id"])
        t = e.get("type", "unknown")
        if eid in god_ids:
            ent_to_cluster[eid] = eid
        elif t not in ("module", "config"):
            ent_to_cluster[eid] = f"cluster_{t}"
        else:
            ent_to_cluster[eid] = None

    # Aggregate edges between clusters
    cluster_edge_counts = {}
    cluster_edge_types = {}
    for r in relationships:
        src = _esc(r["source"])
        tgt = _esc(r["target"])
        sc = ent_to_cluster.get(src)
        tc = ent_to_cluster.get(tgt)
        if sc and tc and sc != tc:
            key = (sc, tc)
            cluster_edge_counts[key] = cluster_edge_counts.get(key, 0) + 1
            if key not in cluster_edge_types:
                cluster_edge_types[key] = set()
            cluster_edge_types[key].add(r.get("type", ""))

    # Create cluster edges
    cluster_edges = []
    sorted_edges = sorted(cluster_edge_counts.items(), key=lambda x: -x[1])[:40]
    for (src, tgt), count in sorted_edges:
        types = cluster_edge_types.get((src, tgt), set())
        label = ", ".join(sorted(types)[:3])
        if len(label) > 30:
            label = label[:27] + "..."
        cluster_edges.append({
            "source": src,
            "target": tgt,
            "label": label,
            "count": count,
            "width": min(count // 10 + 1, 4),
        })

    # Prepare member data for drill-down
    member_data = {}
    for t, ents in type_groups.items():
        if t in ("module", "config"):
            continue
        members = []
        for e in ents[:80]:
            eid = _esc(e["id"])
            members.append({
                "id": eid,
                "name": e.get("name", eid),
                "type": e.get("type", "unknown"),
                "file": e.get("file", ""),
                "size": 6,
                "shape": "diamond" if eid in god_ids else "dot",
            })
        # Add edges between members
        member_edges = []
        for r in relationships:
            src = _esc(r["source"])
            tgt = _esc(r["target"])
            src_ent = entity_map.get(src)
            tgt_ent = entity_map.get(tgt)
            if src_ent and tgt_ent:
                if src_ent.get("type") == t or tgt_ent.get("type") == t:
                    if src != tgt:
                        member_edges.append({
                            "source": src,
                            "target": tgt,
                            "type": r.get("type", ""),
                        })
        member_data[t] = {"nodes": members, "edges": member_edges[:100]}

    vis_js = Path("/tmp/vis-network.min.js").read_text()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; overflow: hidden; }}
#header {{ padding: 10px 20px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }}
#header h1 {{ font-size: 15px; font-weight: 600; }}
#header .stats {{ font-size: 11px; color: #8b949e; }}
#controls {{ padding: 8px 20px; background: #161b22; border-bottom: 1px solid #30363d; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
#controls input {{ background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 8px; border-radius: 4px; width: 200px; font-size: 12px; }}
#controls button {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
#controls button:hover {{ background: #30363d; }}
.breadcrumb {{ display: flex; gap: 4px; align-items: center; font-size: 11px; color: #8b949e; }}
.breadcrumb span {{ cursor: pointer; color: #58a6ff; }}
.breadcrumb span:hover {{ text-decoration: underline; }}
.breadcrumb .sep {{ color: #484f58; cursor: default; }}
.breadcrumb .current {{ color: #c9d1d9; cursor: default; }}
#graph {{ width: 100vw; height: calc(100vh - 80px); }}
#legend {{ position: absolute; bottom: 12px; left: 12px; background: #161b22ee; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px; font-size: 10px; z-index: 10; }}
#legend .item {{ display: flex; align-items: center; gap: 6px; margin: 2px 0; }}
#legend .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
#legend .diamond {{ width: 10px; height: 10px; transform: rotate(45deg); background: #ffd700; }}
#info {{ position: absolute; top: 80px; right: 12px; background: #161b22ee; border: 1px solid #30363d; border-radius: 6px; padding: 12px; width: 300px; max-height: 400px; overflow-y: auto; display: none; font-size: 11px; z-index: 10; }}
#info h3 {{ margin-bottom: 6px; font-size: 12px; color: #fff; word-break: break-all; }}
#info .meta {{ color: #8b949e; margin-bottom: 6px; }}
#info .rel {{ padding: 2px 0; color: #8b949e; border-bottom: 1px solid #21262d; }}
#info .rel-type {{ color: #58a6ff; }}
#status {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #8b949e; font-size: 13px; }}
</style>
</head>
<body>
<div id="header">
  <h1>{title}</h1>
  <div class="stats">{stats_text}</div>
</div>
<div id="controls">
  <input type="text" id="search" placeholder="Search...">
  <button onclick="showOverview()">Overview</button>
  <button onclick="network.fit()">Fit</button>
  <div class="breadcrumb" id="breadcrumb">
    <span class="current">Overview</span>
  </div>
</div>
<div id="graph"></div>
<div id="status">Loading...</div>
<div id="legend">
  <div class="item"><div class="dot" style="background:#58a6ff"></div> Module</div>
  <div class="item"><div class="dot" style="background:#3fb950"></div> Class</div>
  <div class="item"><div class="dot" style="background:#d2a8ff"></div> Function</div>
  <div class="item"><div class="dot" style="background:#f0883e"></div> Route</div>
  <div class="item"><div class="dot" style="background:#f778ba"></div> Schema</div>
  <div class="item"><div class="diamond"></div> God Node</div>
  <div class="item" style="color:#58a6ff">Click cluster to drill down</div>
</div>
<div id="info">
  <h3 id="info-title"></h3>
  <div class="meta" id="info-meta"></div>
  <div id="info-body"></div>
</div>

<script>
{vis_js}
</script>
<script>
const clusterNodes = {json.dumps(cluster_nodes)};
const clusterEdges = {json.dumps(cluster_edges)};
const memberData = {json.dumps(member_data)};
const entityMap = {json.dumps({k: {"name": v.get("name",""), "type": v.get("type",""), "file": v.get("file",""), "id": v["id"]} for k, v in entity_map.items()})};
const allRelationships = {json.dumps([{"source": _esc(r["source"]), "target": _esc(r["target"]), "type": r.get("type","")} for r in relationships])};

const colors = {{
  module: '#58a6ff', class: '#3fb950', function: '#d2a8ff',
  route: '#f0883e', schema: '#f778ba', config: '#8b949e',
  god: '#ffd700', cluster: '#58a6ff', enum: '#ffa657', mixin: '#79c0ff'
}};

const container = document.getElementById('graph');
let network, nodes, edges, currentView = 'overview';

function makeNodes(items) {{
  return new vis.DataSet(items.map(e => ({{
    id: e.id,
    label: e.name.length > 22 ? e.name.substring(0, 20) + '..' : e.name,
    color: {{
      background: colors[e.type] || '#8b949e',
      border: colors[e.type] || '#8b949e',
      highlight: {{ background: '#fff', border: colors[e.type] || '#8b949e' }}
    }},
    font: {{ color: '#c9d1d9', size: e.size > 15 ? 12 : 9, strokeWidth: 2, strokeColor: '#0d1117' }},
    shape: e.shape || 'dot',
    size: e.size || 6,
    title: (e.file || e.type) + '\\nClick to explore'
  }})));
}}

function makeEdges(items) {{
  return new vis.DataSet(items.map(r => ({{
    from: r.source,
    to: r.target,
    label: r.label || r.type || '',
    width: r.width || 1,
    color: {{ color: '#21262d', highlight: '#58a6ff', opacity: 0.6 }},
    font: {{ size: 8, color: '#58a6ff', strokeWidth: 0 }},
    arrows: {{ to: {{ enabled: true, scaleFactor: 0.4 }} }},
    smooth: {{ type: 'curvedCW', roundness: 0.15 }}
  }})));
}}

function initGraph(nodeData, edgeData, opts = {{}}) {{
  if (network) network.destroy();
  nodes = makeNodes(nodeData);
  edges = makeEdges(edgeData);
  network = new vis.Network(container, {{ nodes, edges }}, {{
    physics: {{
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {{
        gravitationalConstant: opts.gravity || -40,
        centralGravity: 0.008,
        springLength: opts.springLength || 120,
        springConstant: 0.06,
        damping: 0.4
      }},
      stabilization: {{ iterations: 60, fit: true }}
    }},
    interaction: {{ hover: true, tooltipDelay: 80, zoomView: true, dragView: true }},
    edges: {{ smooth: false }}
  }});
  window.network = network;

  network.on('click', function(p) {{
    if (p.nodes.length > 0) handleNodeClick(p.nodes[0]);
    else document.getElementById('info').style.display = 'none';
  }});

  network.on('doubleClick', function(p) {{
    if (p.nodes.length > 0) handleNodeDoubleClick(p.nodes[0]);
  }});
}}

function handleNodeClick(nodeId) {{
  const ent = entityMap[nodeId];
  const clNode = clusterNodes.find(n => n.id === nodeId);
  const node = clNode || ent;
  if (!node) return;

  const incoming = allRelationships.filter(r => r.target === nodeId);
  const outgoing = allRelationships.filter(r => r.source === nodeId);

  document.getElementById('info-title').textContent = node.name;
  document.getElementById('info-meta').innerHTML =
    '<div><b>Type:</b> ' + (node.type || 'unknown') + '</div>' +
    '<div><b>File:</b> ' + (node.file || '-') + '</div>';

  let body = '';
  if (clNode && clNode.type === 'cluster') {{
    const t = clNode.entityType;
    const count = memberData[t] ? memberData[t].nodes.length : 0;
    body = '<div style="margin:6px 0"><b>' + count + ' members</b></div>';
    body += '<div style="color:#58a6ff;cursor:pointer" onclick="drillDown(\\'' + t + '\\')">Click cluster name or double-click to drill down</div>';
  }}
  body += '<div style="margin-top:8px"><b>Incoming (' + incoming.length + '):</b></div>';
  incoming.slice(0, 8).forEach(r => {{
    body += '<div class="rel"><span class="rel-type">' + r.type + '</span> ← ' + (r.source.split('_').slice(-1)[0] || r.source) + '</div>';
  }});
  body += '<div style="margin-top:6px"><b>Outgoing (' + outgoing.length + '):</b></div>';
  outgoing.slice(0, 8).forEach(r => {{
    body += '<div class="rel"><span class="rel-type">' + r.type + '</span> → ' + (r.target.split('_').slice(-1)[0] || r.target) + '</div>';
  }});

  document.getElementById('info-body').innerHTML = body;
  document.getElementById('info').style.display = 'block';
}}

function handleNodeDoubleClick(nodeId) {{
  const clNode = clusterNodes.find(n => n.id === nodeId);
  if (clNode && clNode.type === 'cluster') {{
    drillDown(clNode.entityType);
  }}
}}

function drillDown(entityType) {{
  const data = memberData[entityType];
  if (!data) return;

  currentView = entityType;
  updateBreadcrumb(entityType);

  document.getElementById('mode-cluster') && document.getElementById('mode-cluster').classList.remove('active');
  initGraph(data.nodes, data.edges, {{ gravity: -20, springLength: 80 }});
}}

function showOverview() {{
  currentView = 'overview';
  updateBreadcrumb(null);
  initGraph(clusterNodes, clusterEdges, {{ gravity: -40, springLength: 120 }});
  document.getElementById('info').style.display = 'none';
}}

function updateBreadcrumb(entityType) {{
  const bc = document.getElementById('breadcrumb');
  if (!entityType) {{
    bc.innerHTML = '<span class="current">Overview</span>';
  }} else {{
    bc.innerHTML = '<span onclick="showOverview()">Overview</span>' +
      '<span class="sep">/</span>' +
      '<span class="current">' + entityType + '</span>';
  }}
}}

// Search
let searchTimeout;
document.getElementById('search').addEventListener('input', function(e) {{
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {{
    const q = e.target.value.toLowerCase();
    if (!nodes) return;
    if (!q) {{
      nodes.forEach(n => nodes.update({{ id: n.id, hidden: false }}));
      return;
    }}
    const all = currentView === 'overview' ? clusterNodes : (memberData[currentView] || {{ nodes: [] }}).nodes;
    const matchIds = new Set(all.filter(n => n.name.toLowerCase().includes(q)).map(n => n.id));
    nodes.forEach(n => nodes.update({{ id: n.id, hidden: !matchIds.has(n.id) }}));
  }}, 150);
}});

document.getElementById('status').style.display = 'none';
showOverview();
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
