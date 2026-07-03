"""NetworkX graph construction from extracted entities and relationships."""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import networkx as nx
except ImportError:
    nx = None

from codemap.extractors.base import Entity, ExtractionResult, Relationship


class GraphBuilder:
    """Build a NetworkX graph from extraction results."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.entity_files: Dict[str, Set[str]] = defaultdict(set)
        self.entity_degree: Dict[str, int] = defaultdict(int)

    def add_result(self, result: ExtractionResult) -> None:
        """Add an extraction result to the graph."""
        for entity in result.entities:
            if entity.id in self.entities:
                existing = self.entities[entity.id]
                if entity.type != "module":
                    existing.type = entity.type
                existing.metadata.update(entity.metadata)
            else:
                self.entities[entity.id] = entity
            self.entity_files[entity.id].add(entity.file)

        for rel in result.relationships:
            self.relationships.append(rel)
            self.entity_degree[rel.source] += 1
            self.entity_degree[rel.target] += 1

    def build_networkx(self) -> "nx.DiGraph":
        """Build a NetworkX directed graph."""
        if nx is None:
            raise ImportError("networkx is required: pip install networkx")

        G = nx.DiGraph()

        for eid, entity in self.entities.items():
            G.add_node(eid, **{
                "type": entity.type,
                "name": entity.name,
                "file": entity.file,
                "line": entity.line,
                **entity.metadata,
            })

        for rel in self.relationships:
            if rel.source in self.entities and rel.target in self.entities:
                G.add_edge(rel.source, rel.target, **{
                    "type": rel.type,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                    "line": rel.line,
                })

        return G

    def get_god_nodes(self, top_n: int = 10) -> List[Dict]:
        """Find entities with highest degree centrality."""
        if not self.entity_degree:
            return []

        sorted_nodes = sorted(
            self.entity_degree.items(), key=lambda x: x[1], reverse=True
        )[:top_n]

        result = []
        for node_id, degree in sorted_nodes:
            entity = self.entities.get(node_id)
            if entity:
                result.append({
                    "id": node_id,
                    "connections": degree,
                    "name": entity.name,
                    "type": entity.type,
                    "file": entity.file,
                })
        return result

    def get_clusters(self, G: "nx.DiGraph") -> List[Dict]:
        """Get file-based clusters from the graph."""
        clusters = defaultdict(lambda: {"members": [], "description": ""})

        for eid, entity in self.entities.items():
            if entity.type == "module":
                continue
            parts = entity.file.split("/")
            if len(parts) >= 2:
                cluster_key = "/".join(parts[:2])
            else:
                cluster_key = parts[0]
            clusters[cluster_key]["members"].append(eid)

        result = []
        for i, (key, data) in enumerate(sorted(clusters.items())):
            if len(data["members"]) < 2:
                continue
            result.append({
                "id": f"cluster_{i}",
                "name": key.split("/")[-1],
                "members": data["members"],
                "description": f"Files in {key}",
            })
        return result

    def get_stats(self) -> Dict:
        """Get graph statistics."""
        confidence_counts = defaultdict(int)
        type_counts = defaultdict(int)
        rel_type_counts = defaultdict(int)

        for entity in self.entities.values():
            type_counts[entity.type] += 1

        for rel in self.relationships:
            confidence_counts[rel.confidence] += 1
            rel_type_counts[rel.type] += 1

        return {
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "entity_types": dict(type_counts),
            "relationship_types": dict(rel_type_counts),
            "confidence": dict(confidence_counts),
        }

    def to_dict(self, project_info: Dict, clusters: List[Dict],
                god_nodes: List[Dict], surprising_links: List[Dict]) -> Dict:
        """Convert graph to serializable dict."""
        return {
            "project": project_info,
            "entities": [
                {
                    "id": e.id,
                    "type": e.type,
                    "name": e.name,
                    "file": e.file,
                    "line": e.line,
                    "metadata": e.metadata,
                }
                for e in self.entities.values()
            ],
            "relationships": [
                {
                    "source": r.source,
                    "target": r.target,
                    "type": r.type,
                    "confidence": r.confidence,
                    "evidence": r.evidence,
                    "line": r.line,
                }
                for r in self.relationships
            ],
            "clusters": clusters,
            "metadata": {
                "god_nodes": god_nodes,
                "surprising_links": surprising_links,
                **self.get_stats(),
            },
        }
