"""Additional analyzers for graph insights."""

import re
from collections import defaultdict

from projetmap.extractors.base import Entity, Relationship


class LayerViolationAnalyzer:
    """Detect layering violations in the architecture."""

    LAYER_PATTERNS = {
        "ui": re.compile(r"screen|widget|page|view|component", re.I),
        "service": re.compile(r"service|client|repository|provider", re.I),
        "model": re.compile(r"model|schema|entity|dto|data", re.I),
        "database": re.compile(r"database|db|drift|sqlite|supabase", re.I),
    }

    def analyze(self, entities: dict[str, Entity], relationships: list[Relationship]) -> list[dict]:
        violations = []
        for rel in relationships:
            if rel.type != "imports":
                continue
            source = entities.get(rel.source)
            target = entities.get(rel.target)
            if not source or not target:
                continue
            source_layer = self._detect_layer(source)
            target_layer = self._detect_layer(target)
            if source_layer and target_layer:
                layer_order = ["ui", "service", "model", "database"]
                si = layer_order.index(source_layer) if source_layer in layer_order else -1
                ti = layer_order.index(target_layer) if target_layer in layer_order else -1
                if si >= 0 and ti >= 0 and si < ti:
                    violations.append({
                        "source": rel.source,
                        "target": rel.target,
                        "violation": f"{source_layer} layer directly imports {target_layer} layer",
                        "source_layer": source_layer,
                        "target_layer": target_layer,
                    })
        return violations

    def _detect_layer(self, entity: Entity) -> str:
        name = entity.name.lower()
        file = entity.file.lower()
        for layer, pattern in self.LAYER_PATTERNS.items():
            if pattern.search(name) or pattern.search(file):
                return layer
        return ""


class CircularDependencyAnalyzer:
    """Detect circular dependencies in the import graph."""

    def analyze(self, relationships: list[Relationship]) -> list[dict]:
        import networkx as nx

        G = nx.DiGraph()
        for rel in relationships:
            if rel.type == "imports":
                G.add_edge(rel.source, rel.target)

        cycles = []
        try:
            for cycle in nx.simple_cycles(G):
                if len(cycle) > 1:
                    cycles.append({
                        "cycle": cycle,
                        "length": len(cycle),
                        "description": " → ".join(cycle) + " → " + cycle[0],
                    })
        except Exception:
            pass

        return cycles[:10]


class NamingConventionAnalyzer:
    """Check naming convention consistency."""

    def analyze(self, entities: dict[str, Entity]) -> dict:
        issues = defaultdict(list)

        for eid, entity in entities.items():
            if entity.type == "class":
                if not entity.name[0].isupper():
                    issues["class_naming"].append(eid)
            elif entity.type == "function":
                if not entity.name[0].islower() and not entity.name.startswith("_"):
                    issues["function_naming"].append(eid)

        return dict(issues)
