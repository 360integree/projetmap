"""Overlap Detector — Detect redundancies, semantic duplicates, and contradictions.

Three detection strategies:
1. Topic-Intent Collision: Same topic + same intent = redundancy
2. Scope Conflict: Same mandate applied to different scopes = potential conflict
3. Semantic Similarity: Same concept in different words = reworded duplicate
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .classifier import ClassifiedChunk, IntentType


@dataclass
class Redundancy:
    """A detected redundancy between two instruction chunks."""
    chunk_a_id: str
    chunk_b_id: str
    type: str  # topic_collision, scope_conflict, semantic_duplicate, contradiction
    severity: str  # low, medium, high, critical
    shared_topics: set[str] = field(default_factory=set)
    evidence: str = ""
    recommendation: str = ""
    similarity_score: float = 0.0

    @property
    def key(self) -> tuple[str, str, str]:
        """Unique key for deduplication."""
        ids = sorted([self.chunk_a_id, self.chunk_b_id])
        return (ids[0], ids[1], self.type)


@dataclass
class RedundancyCluster:
    """A group of chunks that are all redundant with each other."""
    id: str
    chunk_ids: set[str] = field(default_factory=set)
    topic: str = ""
    avg_similarity: float = 0.0
    severity: str = "medium"
    recommendation: str = ""


class OverlapDetector:
    """Detect instruction redundancies and conflicts."""

    # Similarity thresholds
    TOPIC_COLLISION_THRESHOLD = 1  # Minimum shared topics
    SEMANTIC_SIMILARITY_THRESHOLD = 0.65  # Minimum cosine similarity
    HIGH_SIMILARITY_THRESHOLD = 0.80  # High similarity threshold

    def detect_all(
        self, classified_chunks: list[ClassifiedChunk],
    ) -> tuple[list[Redundancy], list[RedundancyCluster]]:
        """Run all detection strategies and return results."""
        redundancies = []

        # Strategy 1: Topic-Intent Collision
        topic_redundancies = self._detect_topic_collisions(classified_chunks)
        redundancies.extend(topic_redundancies)

        # Strategy 2: Scope Conflicts
        scope_conflicts = self._detect_scope_conflicts(classified_chunks)
        redundancies.extend(scope_conflicts)

        # Strategy 3: Semantic Similarity (keyword-based, no embeddings needed)
        semantic_dups = self._detect_semantic_duplicates(classified_chunks)
        redundancies.extend(semantic_dups)

        # Strategy 4: Contradiction Detection
        contradictions = self._detect_contradictions(classified_chunks)
        redundancies.extend(contradictions)

        # Deduplicate
        seen_keys = set()
        unique = []
        for r in redundancies:
            if r.key not in seen_keys:
                seen_keys.add(r.key)
                unique.append(r)

        # Cluster
        clusters = self._cluster_redundancies(unique, classified_chunks)

        return unique, clusters

    def _detect_topic_collisions(
        self, chunks: list[ClassifiedChunk],
    ) -> list[Redundancy]:
        """Detect chunks with same topic + same intent = redundancy."""
        redundancies = []

        # Group by (primary_intent, frozenset(topics))
        groups = defaultdict(list)
        for cc in chunks:
            if cc.primary_intent in (IntentType.CONSTRAINT, IntentType.MANDATE):
                key = (cc.primary_intent, frozenset(cc.chunk.topics))
                groups[key].append(cc)

        for (intent, topics), group in groups.items():
            if len(group) < 2:
                continue

            # Check every pair in the group
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    shared = a.chunk.topics & b.chunk.topics

                    if len(shared) >= self.TOPIC_COLLISION_THRESHOLD:
                        severity = "high" if intent == IntentType.MANDATE else "medium"
                        # If both are about "inquiry" behavior, that's the classic "always ask" pattern
                        if shared == {"inquiry"} or shared >= {"inquiry", "education"}:
                            severity = "high"

                        redundancies.append(Redundancy(
                            chunk_a_id=a.chunk.id,
                            chunk_b_id=b.chunk.id,
                            type="topic_collision",
                            severity=severity,
                            shared_topics=shared,
                            evidence=f"Both {intent.value} about {', '.join(sorted(shared))}",
                            recommendation=f"Consolidate into single {intent.value} with lifecycle scope guards",
                        ))

        return redundancies

    def _detect_scope_conflicts(
        self, chunks: list[ClassifiedChunk],
    ) -> list[Redundancy]:
        """Detect same mandate applied to different scopes = potential conflict."""
        redundancies = []

        # Group by primary topic
        topic_groups = defaultdict(list)
        for cc in chunks:
            if cc.primary_intent in (IntentType.MANDATE, IntentType.CONSTRAINT):
                for topic in cc.chunk.topics:
                    topic_groups[topic].append(cc)

        for topic, group in topic_groups.items():
            if len(group) < 2:
                continue

            # Check for scope differences
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]

                    # Different scopes + same topic = potential conflict
                    scopes_a = a.chunk.scope_tags
                    scopes_b = b.chunk.scope_tags

                    if scopes_a and scopes_b and not scopes_a.intersection(scopes_b):
                        # Completely disjoint scopes - might conflict
                        # Example: "ALWAYS ask age" (global) vs "NEVER ask age for settled" (settled)
                        redundancies.append(Redundancy(
                            chunk_a_id=a.chunk.id,
                            chunk_b_id=b.chunk.id,
                            type="scope_conflict",
                            severity="medium",
                            shared_topics={topic},
                            evidence=f"Scope conflict: {scopes_a} vs {scopes_b} on '{topic}'",
                            recommendation=f"Add scope guard to disambiguate: '{topic}' applies to {scopes_a} but not {scopes_b}",
                        ))

        return redundancies

    def _detect_semantic_duplicates(
        self, chunks: list[ClassifiedChunk],
    ) -> list[Redundancy]:
        """Detect reworded duplicates using keyword-based similarity."""
        redundancies = []

        # Build keyword sets for each chunk
        chunk_keywords = []
        for cc in chunks:
            keywords = self._extract_keywords(cc.chunk.text)
            chunk_keywords.append((cc, keywords))

        # Compare pairs
        for i in range(len(chunk_keywords)):
            for j in range(i + 1, len(chunk_keywords)):
                cc_a, kw_a = chunk_keywords[i]
                cc_b, kw_b = chunk_keywords[j]

                if not kw_a or not kw_b:
                    continue

                # Jaccard similarity
                intersection = kw_a & kw_b
                union = kw_a | kw_b
                similarity = len(intersection) / len(union) if union else 0.0

                if similarity >= self.SEMANTIC_SIMILARITY_THRESHOLD:
                    severity = "high" if similarity >= self.HIGH_SIMILARITY_THRESHOLD else "medium"

                    redundancies.append(Redundancy(
                        chunk_a_id=cc_a.chunk.id,
                        chunk_b_id=cc_b.chunk.id,
                        type="semantic_duplicate",
                        severity=severity,
                        shared_topics=cc_a.chunk.topics & cc_b.chunk.topics,
                        evidence=f"Keyword similarity: {similarity:.0%} ({len(intersection)} shared keywords)",
                        recommendation="Consolidate into single instruction or cross-reference",
                        similarity_score=similarity,
                    ))

        return redundancies

    def _detect_contradictions(
        self, chunks: list[ClassifiedChunk],
    ) -> list[Redundancy]:
        """Detect instructions that contradict each other."""
        redundancies = []

        for i in range(len(chunks)):
            for j in range(i + 1, len(chunks)):
                a, b = chunks[i], chunks[j]

                # Same topic, one says "always" other says "never skip" = potential conflict
                if (a.primary_intent == IntentType.MANDATE and
                    b.primary_intent == IntentType.MANDATE):
                    shared = a.chunk.topics & b.chunk.topics
                    if shared:
                        # Check for conflicting scope
                        scopes_a = a.chunk.scope_tags - {"global", "turn_specific"}
                        scopes_b = b.chunk.scope_tags - {"global", "turn_specific"}
                        if scopes_a and scopes_b and not scopes_a.intersection(scopes_b):
                            redundancies.append(Redundancy(
                                chunk_a_id=a.chunk.id,
                                chunk_b_id=b.chunk.id,
                                type="contradiction",
                                severity="high",
                                shared_topics=shared,
                                evidence=f"Conflicting mandates for different scopes: {scopes_a} vs {scopes_b}",
                                recommendation="Add scope guards to disambiguate",
                            ))

        return redundancies

    def _looks_like_negation(self, text_a: str, text_b: str) -> bool:
        """Check if text_a negates text_b — only for specific behavioral contradictions."""
        # Only flag if both texts discuss the SAME specific behavior
        # e.g., "NEVER ask about X" vs "ALWAYS ask about X"
        # NOT: "NEVER assume" vs "ALWAYS ask" (different behaviors)

        # Extract the key action phrases from each
        a_action = self._extract_action_phrase(text_a)
        b_action = self._extract_action_phrase(text_b)

        if not a_action or not b_action:
            return False

        # Actions must be similar (same topic) but opposite polarity
        if a_action == b_action:
            a_polarity = self._get_polarity(text_a)
            b_polarity = self._get_polarity(text_b)
            return a_polarity != b_polarity

        return False

    def _extract_action_phrase(self, text: str) -> str:
        """Extract the core action phrase from an instruction."""
        # Look for common instruction patterns
        patterns = [
            r"(?:never|always|must|must not|do not|skip)\s+([\w\s]{3,30}?)(?:\.|,|for|when|if|$)",
            r"(?:ask|skip|assume|include|avoid)\s+([\w\s]{3,30}?)(?:\.|,|for|when|if|$)",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().lower()
        return ""

    def _get_polarity(self, text: str) -> str:
        """Get the polarity (positive/negative) of an instruction."""
        negative = bool(re.search(r"\b(never|do not|must not|skip|avoid)\b", text, re.IGNORECASE))
        positive = bool(re.search(r"\b(always|must|required|mandatory|include|ask)\b", text, re.IGNORECASE))
        if negative:
            return "negative"
        if positive:
            return "positive"
        return "neutral"

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from text for similarity comparison."""
        # Remove common stop words and short words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "out", "off", "over",
            "under", "again", "further", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "because", "but", "and",
            "or", "if", "while", "that", "this", "these", "those", "it", "its",
            "you", "your", "yours", "we", "our", "ours", "they", "their", "theirs",
            "what", "which", "who", "whom", "whose", "i", "me", "my", "mine",
            "also", "about", "up", "down", "still", "already", "yet", "ever",
            "let", "make", "sure", "must", "should", "need", "use", "like",
            "want", "going", "get", "got", "take", "see", "know", "think",
        }

        # Tokenize
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())

        # Filter stop words
        keywords = set(w for w in words if w not in stop_words)

        return keywords

    def _cluster_redundancies(
        self, redundancies: list[Redundancy], chunks: list[ClassifiedChunk],
    ) -> list[RedundancyCluster]:
        """Group redundancies into clusters of mutually redundant chunks."""
        if not redundancies:
            return []

        # Build adjacency: chunk_id -> set of chunk_ids it's redundant with
        adjacency = defaultdict(set)
        for r in redundancies:
            adjacency[r.chunk_a_id].add(r.chunk_b_id)
            adjacency[r.chunk_b_id].add(r.chunk_a_id)

        # Find connected components (clusters)
        visited = set()
        clusters = []

        for chunk_id in adjacency:
            if chunk_id in visited:
                continue

            # BFS to find all connected chunks
            cluster_members = set()
            queue = [chunk_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster_members.add(current)
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(cluster_members) < 2:
                continue

            # Find the dominant topic
            topic_counts = defaultdict(int)
            for cid in cluster_members:
                for cc in chunks:
                    if cc.chunk.id == cid:
                        for topic in cc.chunk.topics:
                            topic_counts[topic] += 1

            dominant_topic = max(topic_counts, key=topic_counts.get) if topic_counts else "unknown"

            # Calculate average similarity
            similarities = [
                r.similarity_score for r in redundancies
                if r.chunk_a_id in cluster_members and r.chunk_b_id in cluster_members
                and r.similarity_score > 0
            ]
            avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

            # Determine cluster severity
            severities = [
                r.severity for r in redundancies
                if r.chunk_a_id in cluster_members and r.chunk_b_id in cluster_members
            ]
            if "critical" in severities:
                severity = "critical"
            elif "high" in severities:
                severity = "high"
            else:
                severity = "medium"

            clusters.append(RedundancyCluster(
                id=f"cluster_{len(clusters)}",
                chunk_ids=cluster_members,
                topic=dominant_topic,
                avg_similarity=avg_sim,
                severity=severity,
                recommendation=f"Consolidate {len(cluster_members)} chunks about '{dominant_topic}' into single source of truth",
            ))

        return clusters
