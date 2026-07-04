"""Core journey detection algorithm — 5 phases: entry points, handlers, call chains, classification, grouping."""

import re
from collections import defaultdict, deque
from pathlib import Path

from projetmap.journeys.classifier import classify_step
from projetmap.journeys.models import Journey, JourneyReport, JourneyStep, StepType

# Minimum steps for a valid journey
MIN_JOURNEY_STEPS = 3
# Minimum confidence to report
MIN_CONFIDENCE = 0.3
# Max BFS depth
MAX_DEPTH = 8
# Confidence decay per hop
CONFIDENCE_DECAY = 0.85
# Threshold for confidence before pruning
CONFIDENCE_THRESHOLD = 0.2
# Deduplication: merge journeys sharing > this fraction of steps
DEDUP_OVERLAP = 0.7


def _esc(s: str) -> str:
    """Escape entity ID for safe use as graph node key."""
    return s.replace("/", "_").replace(".", "_").replace("-", "_").replace(" ", "_")


class JourneyDetector:
    """Detect user journeys from a knowledge graph."""

    def detect(self, graph_data: dict) -> JourneyReport:
        """Run the full 5-phase detection pipeline.

        Args:
            graph_data: The full graph data dict from GraphBuilder.to_dict().

        Returns:
            JourneyReport with all discovered journeys.
        """
        entities_list = graph_data.get("entities", [])
        relationships = graph_data.get("relationships", [])

        # Build entity lookup
        entities: dict[str, dict] = {}
        for e in entities_list:
            entities[e["id"]] = e

        # Phase 1: Find UI entry points
        entry_points = self._find_ui_entry_points(entities, relationships)

        # Phase 2: Find event handlers for each entry point
        all_journeys: list[Journey] = []
        seen_handler_chains: set[tuple] = set()

        for ep in entry_points:
            handlers = self._find_event_handlers(ep["id"], entities, relationships)
            for handler in handlers:
                # Phase 3: Trace call chain from handler
                steps = self._trace_journey(handler["id"], entities, relationships)
                if len(steps) < MIN_JOURNEY_STEPS:
                    continue

                # Deduplicate: skip if we've seen this exact chain
                chain_key = tuple(s["id"] for s in steps)
                if chain_key in seen_handler_chains:
                    continue
                seen_handler_chains.add(chain_key)

                # Phase 4: Build JourneyStep objects with classifications
                journey_steps = self._build_journey_steps(steps, entities, relationships)

                # Phase 5: Score and create journey
                journey = self._create_journey(
                    ep, handler, journey_steps, entities
                )
                if journey.confidence >= MIN_CONFIDENCE:
                    all_journeys.append(journey)

        # Deduplication pass: merge overlapping journeys
        all_journeys = self._deduplicate_journeys(all_journeys)

        # Group by feature
        self._group_by_feature(all_journeys)

        # Build report
        return self._build_report(all_journeys, len(entities))

    def _find_ui_entry_points(
        self, entities: dict[str, dict], relationships: list[dict]
    ) -> list[dict]:
        """Phase 1: Find all user-visible entry points in the graph."""
        entry_points = []

        # Collect targets of routes_to relationships
        routes_to_targets = set()
        for r in relationships:
            if r.get("type") == "routes_to":
                routes_to_targets.add(r["target"])

        for eid, entity in entities.items():
            score = 0.0
            reason = ""

            # Direct route entity
            if entity.get("type") == "route":
                score = 0.9
                reason = "route entity"

            # Screen/Page/View/Widget/Component class
            name = entity.get("name", "")
            if re.search(r"(Screen|Page|View|Widget|Component)$", name):
                score = max(score, 0.85)
                reason = "UI component naming"

            # Has incoming routes_to relationship
            if eid in routes_to_targets:
                score = max(score, 0.8)
                reason = "has routes_to incoming"

            if score > 0:
                entry_points.append({
                    "id": eid,
                    "entity": entity,
                    "score": score,
                    "reason": reason,
                })

        return sorted(entry_points, key=lambda x: -x["score"])

    def _find_event_handlers(
        self,
        entity_id: str,
        entities: dict[str, dict],
        relationships: list[dict],
    ) -> list[dict]:
        """Phase 2: Find event handler methods associated with a UI entry point."""
        handlers = []
        entity = entities.get(entity_id, {})
        entity_file = entity.get("file", "")

        handler_patterns = [
            re.compile(r"^on[A-Z]\w*"),
            re.compile(r"^handle[A-Z]\w*"),
            re.compile(r"^_on[A-Z]\w*"),
            re.compile(r"^(tap|click|submit|press|change|input|scroll|swipe)\w*", re.I),
        ]

        for eid, e in entities.items():
            if eid == entity_id:
                continue
            if e.get("file") != entity_file:
                continue
            if e.get("type") != "function":
                continue

            name = e.get("name", "")
            for pattern in handler_patterns:
                if pattern.search(name):
                    # Check if this function is called from the entry point
                    has_call = any(
                        r.get("source") == entity_id
                        and r.get("target") == eid
                        and r.get("type") == "calls"
                        for r in relationships
                    )
                    handlers.append({
                        "id": eid,
                        "name": name,
                        "confidence": 0.8 if has_call else 0.5,
                        "reason": f"handler pattern: {name}",
                    })
                    break

        return handlers

    def _trace_journey(
        self,
        handler_id: str,
        entities: dict[str, dict],
        relationships: list[dict],
    ) -> list[dict]:
        """Phase 3: BFS from a handler through call and navigation relationships."""
        steps = []
        visited = set()
        queue = deque([(handler_id, 0, 1.0)])

        # Build adjacency for quick lookup
        adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for r in relationships:
            rtype = r.get("type", "")
            if rtype in ("calls", "routes_to"):
                adj[r["source"]].append((r["target"], rtype))

        while queue:
            node_id, depth, conf = queue.popleft()
            if node_id in visited or depth > MAX_DEPTH:
                continue
            if node_id not in entities:
                continue
            visited.add(node_id)

            entity = entities[node_id]
            out_edge_types = {rtype for _, rtype in adj.get(node_id, [])}

            steps.append({
                "id": node_id,
                "entity": entity,
                "depth": depth,
                "confidence": conf,
                "out_edge_types": out_edge_types,
            })

            # Follow call and routes_to edges
            for target, rtype in adj.get(node_id, []):
                new_conf = conf * CONFIDENCE_DECAY
                if new_conf > CONFIDENCE_THRESHOLD and target not in visited:
                    queue.append((target, depth + 1, new_conf))

        return steps

    def _build_journey_steps(
        self,
        raw_steps: list[dict],
        entities: dict[str, dict],
        relationships: list[dict],
    ) -> list[JourneyStep]:
        """Phase 4: Build JourneyStep objects with type classifications."""
        journey_steps = []
        for raw in raw_steps:
            node_id = raw["id"]
            entity = raw["entity"]
            step_type = classify_step(
                node_id, entity, raw.get("out_edge_types", set())
            )
            journey_steps.append(JourneyStep(
                id=_esc(node_id),
                node_id=node_id,
                step_type=step_type,
                name=entity.get("name", node_id),
                file=entity.get("file", ""),
                line=entity.get("line", 0),
                confidence=raw["confidence"],
            ))
        return journey_steps

    def _create_journey(
        self,
        entry_point: dict,
        handler: dict,
        steps: list[JourneyStep],
        entities: dict[str, dict],
    ) -> Journey:
        """Phase 5: Create a Journey object with confidence scoring."""
        ep_name = entry_point["entity"].get("name", entry_point["id"])
        handler_name = handler.get("name", "")

        # Generate journey ID and name
        journey_id = f"{_esc(entry_point['id'])}__{_esc(handler.get('id', ''))}"
        journey_name = f"{ep_name} → {handler_name}" if handler_name else ep_name

        # Compute confidence
        confidence = self._compute_confidence(steps)

        # Collect step types present
        step_types = list(dict.fromkeys(s.step_type for s in steps))

        # Primary file: entry point file
        primary_file = entry_point["entity"].get("file", "")

        return Journey(
            id=journey_id,
            name=journey_name,
            feature="",  # Filled in by _group_by_feature
            steps=steps,
            entry_point=entry_point["id"],
            confidence=confidence,
            step_types_present=step_types,
            file=primary_file,
        )

    def _compute_confidence(self, steps: list[JourneyStep]) -> float:
        """Compute overall journey confidence from step confidences."""
        if not steps:
            return 0.0

        step_confs = [s.confidence for s in steps]
        avg_conf = sum(step_confs) / len(step_confs)

        # Bonus for diverse step types
        type_diversity = len(set(s.step_type for s in steps)) / len(StepType)
        type_bonus = type_diversity * 0.15

        # Penalty for short journeys
        length_factor = min(len(steps) / 3, 1.0)

        return min(avg_conf * length_factor + type_bonus, 1.0)

    def _deduplicate_journeys(self, journeys: list[Journey]) -> list[Journey]:
        """Merge journeys that share >70% of their steps."""
        if not journeys:
            return journeys

        # Sort by confidence descending
        journeys.sort(key=lambda j: -j.confidence)
        merged: list[Journey] = []
        used: set[int] = set()

        for i, j1 in enumerate(journeys):
            if i in used:
                continue
            for j2_idx in range(i + 1, len(journeys)):
                if j2_idx in used:
                    continue
                j2 = journeys[j2_idx]
                overlap = self._step_overlap(j1.steps, j2.steps)
                if overlap > DEDUP_OVERLAP:
                    # Merge: keep the higher-confidence one, add unique steps from the other
                    used.add(j2_idx)
            merged.append(j1)

        return merged

    def _step_overlap(self, steps_a: list[JourneyStep], steps_b: list[JourneyStep]) -> float:
        """Compute fraction of steps shared between two journeys."""
        ids_a = {s.node_id for s in steps_a}
        ids_b = {s.node_id for s in steps_b}
        if not ids_a or not ids_b:
            return 0.0
        intersection = ids_a & ids_b
        union = ids_a | ids_b
        return len(intersection) / len(union) if union else 0.0

    def _group_by_feature(self, journeys: list[Journey]) -> None:
        """Group journeys by inferred feature name."""
        for j in journeys:
            j.feature = self._infer_feature(j)

    def _infer_feature(self, journey: Journey) -> str:
        """Infer a feature name from the journey's entry point or file path."""
        # Try to extract from entry point name
        ep_name = journey.entry_point
        # Remove common suffixes
        for suffix in ("Screen", "Page", "View", "Widget", "Component"):
            if ep_name.endswith(suffix):
                return ep_name[: -len(suffix)]

        # Fall back to file path
        if journey.file:
            parts = Path(journey.file).parts
            # Use the most meaningful directory or file name
            for part in reversed(parts):
                if part not in ("lib", "src", "app", "apps", "packages", "lib/src"):
                    stem = Path(part).stem
                    return stem

        return "General"

    def _build_report(
        self, journeys: list[Journey], entity_count: int
    ) -> JourneyReport:
        """Build the final JourneyReport."""
        by_feature: dict[str, int] = defaultdict(int)
        by_step_type: dict[str, int] = defaultdict(int)
        conf_dist: dict[str, int] = defaultdict(int)

        for j in journeys:
            by_feature[j.feature] += 1
            for st in j.step_types_present:
                by_step_type[st.value] += 1
            # Confidence distribution buckets
            if j.confidence >= 0.8:
                conf_dist["high (>=0.8)"] += 1
            elif j.confidence >= 0.5:
                conf_dist["medium (0.5-0.8)"] += 1
            else:
                conf_dist["low (<0.5)"] += 1

        return JourneyReport(
            journeys=journeys,
            total_journeys=len(journeys),
            by_feature=dict(by_feature),
            by_step_type=dict(by_step_type),
            confidence_distribution=dict(conf_dist),
            files_analyzed=entity_count,
        )
