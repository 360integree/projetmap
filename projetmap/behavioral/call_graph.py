"""Call graph analysis — language-agnostic dead code, hot paths, call depth.

This module consumes the standard behavioral_data.json schema and detects:
- Dead code (functions unreachable from entry points)
- Hot paths (most-called functions within the project)
- Deep call chains (longest paths, potential stack overflow risk)

Language-specific extractors provide:
  - call_graph: { "file::method": { "calls": [...], "called_by": [...] } }
  - entry_points: [ { "file": ..., "line": ..., "type": "main" } ]

The analysis is entirely language-agnostic — it operates on the graph structure.
"""

from collections import defaultdict, deque


def analyze_call_graph(behavioral_data: dict, graph_data: dict) -> dict:
    """Analyze the call graph for dead code, hot paths, and call depth.

    Args:
        behavioral_data: Raw data from any language's behavioral extractor.
        graph_data: Structural graph data (for cross-reference).

    Returns:
        Dict with dead_code, hot_paths, call_depth keys.
    """
    raw_cg = behavioral_data.get('call_graph', {})
    entry_points = behavioral_data.get('entry_points', [])

    # ── Build adjacency list ──────────────────────────────────────────
    adj: dict[str, list[str]] = defaultdict(list)
    all_nodes: set[str] = set()

    for caller, data in raw_cg.items():
        all_nodes.add(caller)
        calls = data.get('calls', [])
        for call in calls:
            target = call['target']
            adj[caller].append(target)
            all_nodes.add(target)

    # ── 1. Dead code detection (BFS from entry points) ────────────────
    reachable: set[str] = set()
    queue: deque = deque()

    # Seed from entry points — match by file path prefix
    for ep in entry_points:
        ep_file = ep.get('file', '')
        for node in all_nodes:
            if node.startswith(ep_file + '::'):
                queue.append(node)
                reachable.add(node)

    # Also seed from common entry patterns (language-agnostic)
    # Any node whose method name looks like an entry point
    entry_method_names = {
        'main', 'run', 'start', 'init', 'setup', 'configure',
        'componentDidMount', 'ngOnInit', 'mounted', 'useEffect',
    }
    for node in all_nodes:
        if '::' in node:
            method = node.split('::')[1]
            if method in entry_method_names:
                queue.append(node)
                reachable.add(node)

    # BFS traversal
    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)

    # Dead code = project-local nodes never reached from any entry point
    dead_code = []
    for node in sorted(all_nodes):
        if node in reachable:
            continue
        # Skip external dependencies (no '::' = not a project function)
        if '::' not in node:
            continue
        has_calls = len(adj.get(node, [])) > 0
        is_called = any(node in targets for targets in adj.values())
        if has_calls or is_called:
            file_path = node.split('::')[0]
            method = node.split('::')[1]
            dead_code.append({
                'function': method,
                'file': file_path,
                'calls_count': len(adj.get(node, [])),
                'called_by_count': sum(1 for t in adj.values() if node in t),
            })

    # ── 2. Hot path detection (in-degree ranking, project-local only) ─
    in_degree: dict[str, int] = defaultdict(int)
    for caller, targets in adj.items():
        for target in targets:
            in_degree[target] += 1

    hot_paths = []
    for node, degree in sorted(in_degree.items(), key=lambda x: -x[1]):
        if degree < 3:
            break
        # Only include project-local functions
        if '::' not in node:
            continue
        file_path = node.split('::')[0]
        method = node.split('::')[1]
        hot_paths.append({
            'function': method,
            'file': file_path,
            'callers': degree,
        })
        if len(hot_paths) >= 15:
            break

    # ── 3. Call depth analysis (longest chains, project-local only) ────
    memo: dict[str, int] = {}

    def dfs_depth(node: str, visited: set[str]) -> int:
        if node in memo:
            return memo[node]
        if node in visited:
            return 0
        visited.add(node)
        max_depth = 0
        for neighbor in adj.get(node, []):
            depth = dfs_depth(neighbor, visited.copy())
            max_depth = max(max_depth, depth + 1)
        memo[node] = max_depth
        return max_depth

    depths = {}
    for node in all_nodes:
        if '::' not in node:
            continue
        if node in adj:
            depths[node] = dfs_depth(node, set())

    deep_chains = []
    for node, depth in sorted(depths.items(), key=lambda x: -x[1])[:10]:
        if depth < 3:
            break
        file_path = node.split('::')[0]
        method = node.split('::')[1]
        deep_chains.append({
            'function': method,
            'file': file_path,
            'depth': depth,
        })

    return {
        'dead_code': dead_code[:30],
        'hot_paths': hot_paths,
        'call_depth': deep_chains,
    }
