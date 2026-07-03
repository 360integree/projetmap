"""State flow analysis — language-agnostic mutation chains, listener health, lifecycle.

This module consumes the standard behavioral_data.json schema and detects:
- State mutation hotspots (classes/files with most mutations)
- Unpaired listeners (add without matching remove = potential memory leaks)
- Lifecycle component summary (which components override lifecycle hooks)
- State container → listener chains

Language-specific extractors map their framework's concepts to this schema:
  - Flutter: ChangeNotifier → state_container, setState → mutation, addListener → listener
  - React: useState → state_container, setState → mutation, useEffect cleanup → listener
  - Python: dataclass → state_container, __setattr__ → mutation
  - Any:   state_container, mutation, listener are the universal primitives
"""

from collections import defaultdict
from typing import Dict, List


def analyze_state_flow(behavioral_data: Dict) -> Dict:
    """Analyze state mutation patterns and component lifecycle health.

    Args:
        behavioral_data: Raw data from any language's behavioral extractor.

    Returns:
        Dict with mutation_hotspots, unpaired_listeners, notify_chains,
        lifecycle_summary, provider_deps keys.
    """
    mutations = behavioral_data.get('state_mutations', [])
    components = behavioral_data.get('widget_lifecycle', [])
    providers = behavioral_data.get('providers', [])
    state_containers = behavioral_data.get('change_notifiers', [])

    # ── 1. Mutation hotspots (classes/files with most mutations) ───────
    class_mutations: Dict[str, Dict] = defaultdict(lambda: {
        'count': 0, 'types': defaultdict(int), 'file': '', 'methods': set()
    })

    for m in mutations:
        # Use enclosing_class if available, else enclosing_method, else 'unknown'
        cls = (m.get('enclosing_class', '')
               or m.get('enclosing_method', '')
               or 'unknown')
        entry = class_mutations[cls]
        entry['count'] += 1
        entry['types'][m['type']] += 1
        entry['file'] = m.get('file', '')
        entry['methods'].add(m.get('enclosing_method', ''))

    hotspots = []
    for cls, data in sorted(class_mutations.items(), key=lambda x: -x[1]['count']):
        if data['count'] < 2:
            break
        count = data['count']
        # Risk heuristic: mutation count + presence of listener-style mutations
        listener_mutations = sum(
            data['types'].get(t, 0)
            for t in ['notifyListeners', 'emit', 'setState', 'update', 'set']
        )
        has_listeners = data['types'].get('addListener', 0) > 0

        if count >= 10:
            risk = 'High'
        elif count >= 5 or (listener_mutations >= 3 and has_listeners):
            risk = 'Medium'
        else:
            risk = 'Low'

        hotspots.append({
            'class': cls,
            'file': data['file'],
            'mutations': count,
            'breakdown': dict(data['types']),
            'risk': risk,
            'risk_reason': (
                f'{count} mutations'
                + (f', {listener_mutations} notify-style' if listener_mutations else '')
                + (', has listeners' if has_listeners else '')
            ),
        })

    # ── 2. Unpaired listeners (memory leak detection) ─────────────────
    add_by_class: Dict[str, List[Dict]] = defaultdict(list)
    remove_by_class: Dict[str, List[Dict]] = defaultdict(list)

    for m in mutations:
        cls = m.get('enclosing_class', '') or m.get('enclosing_method', '') or 'unknown'
        if m['type'] == 'addListener':
            add_by_class[cls].append(m)
        elif m['type'] == 'removeListener':
            remove_by_class[cls].append(m)

    unpaired = []
    all_classes = set(add_by_class.keys()) | set(remove_by_class.keys())
    for cls in all_classes:
        adds = add_by_class.get(cls, [])
        removes = remove_by_class.get(cls, [])
        add_count = len(adds)
        remove_count = len(removes)

        if add_count > 0:
            paired = min(add_count, remove_count)
            unpaired_count = add_count - paired

            if unpaired_count > 0:
                add_contexts = [a.get('context', 'other') for a in adds[paired:]]
                unpaired.append({
                    'component': cls,
                    'file': adds[0].get('file', ''),
                    'listeners_added': add_count,
                    'listeners_removed': remove_count,
                    'unpaired': unpaired_count,
                    'contexts': add_contexts,
                    'status': '⚠️ Unpaired',
                })
            else:
                unpaired.append({
                    'component': cls,
                    'file': adds[0].get('file', ''),
                    'listeners_added': add_count,
                    'listeners_removed': remove_count,
                    'unpaired': 0,
                    'status': '✅ Paired',
                })

    # ── 3. State container → listener chains ───────────────────────────
    notify_chains = []
    for sc in state_containers:
        cls_name = sc.get('class', '')
        file = sc.get('file', '')

        # Find components that might listen (heuristic: override lifecycle hooks)
        listening_components = []
        for w in components:
            overrides = w.get('overrides', [])
            if any(hook in overrides for hook in ['initState', 'componentDidMount', 'ngOnInit', 'useEffect']):
                listening_components.append(w.get('widget', w.get('component', '')))

        notify_chains.append({
            'state_container': cls_name,
            'file': file,
            'extends': sc.get('extends', ''),
            'potential_listeners': listening_components[:5],
        })

    # ── 4. Lifecycle summary ──────────────────────────────────────────
    # Map common lifecycle hook names across frameworks
    hook_names = {
        'init': ['initState', 'componentDidMount', 'ngOnInit', 'mounted', 'useEffect'],
        'dispose': ['dispose', 'componentWillUnmount', 'ngOnDestroy', 'cleanup', 'unmounted'],
        'update': ['didUpdateWidget', 'componentDidUpdate', 'ngOnChanges', 'shouldComponentUpdate'],
        'build': ['build', 'render', 'template', 'view'],
        'state_change': ['setState', 'forceUpdate', 'markNeedsBuild', 'scheduleRebuild'],
    }

    lifecycle_summary = {
        'total_components': len(components),
    }
    for hook_key, hook_names_list in hook_names.items():
        count = sum(
            1 for c in components
            if any(h in c.get('overrides', []) for h in hook_names_list)
        )
        lifecycle_summary[f'with_{hook_key}'] = count

    # ── 5. Provider/dependency map ────────────────────────────────────
    provider_deps = []
    for p in providers:
        provider_deps.append({
            'type': p.get('type', ''),
            'notifier_class': p.get('notifier_class', ''),
            'state_type': p.get('state_type', ''),
            'file': p.get('file', ''),
            'enclosing_class': p.get('enclosing_class', ''),
        })

    return {
        'mutation_hotspots': hotspots,
        'unpaired_listeners': unpaired,
        'notify_chains': notify_chains,
        'lifecycle_summary': lifecycle_summary,
        'provider_deps': provider_deps,
    }
