"""Instruction Graph Builder — Full pipeline for instruction analysis.

Orchestrates: Chunking → Classification → Overlap Detection → Graph Construction
Outputs a structured instruction_graph that integrates with the main graph.json.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .chunker import InstructionChunk, InstructionChunker
from .classifier import ClassifiedChunk, IntentClassifier, IntentType
from .overlap_detector import OverlapDetector, Redundancy, RedundancyCluster
from .prompt_extractor import PromptExtractor


@dataclass
class InstructionGraph:
    """The complete instruction analysis result."""
    source_file: str
    chunks: List[ClassifiedChunk] = field(default_factory=list)
    redundancies: List[Redundancy] = field(default_factory=list)
    clusters: List[RedundancyCluster] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "source_file": self.source_file,
            "summary": self.summary,
            "chunks": [
                {
                    "id": cc.chunk.id,
                    "text": cc.chunk.text[:200] + "..." if len(cc.chunk.text) > 200 else cc.chunk.text,
                    "line_range": [cc.chunk.line_start, cc.chunk.line_end],
                    "heading": cc.chunk.heading,
                    "heading_level": cc.chunk.heading_level,
                    "topics": sorted(cc.chunk.topics),
                    "question_ids": sorted(cc.chunk.question_ids),
                    "scope_tags": sorted(cc.chunk.scope_tags),
                    "word_count": cc.chunk.word_count,
                    "intents": sorted(i.value for i in cc.intents),
                    "primary_intent": cc.primary_intent.value,
                    "confidence": round(cc.confidence, 2),
                    "severity": cc.severity,
                }
                for cc in self.chunks
            ],
            "redundancies": [
                {
                    "chunk_a": r.chunk_a_id,
                    "chunk_b": r.chunk_b_id,
                    "type": r.type,
                    "severity": r.severity,
                    "shared_topics": sorted(r.shared_topics),
                    "evidence": r.evidence,
                    "recommendation": r.recommendation,
                    "similarity_score": round(r.similarity_score, 2),
                }
                for r in self.redundancies
            ],
            "clusters": [
                {
                    "id": c.id,
                    "chunk_ids": sorted(c.chunk_ids),
                    "topic": c.topic,
                    "avg_similarity": round(c.avg_similarity, 2),
                    "severity": c.severity,
                    "recommendation": c.recommendation,
                }
                for c in self.clusters
            ],
        }


class InstructionGraphBuilder:
    """Full pipeline for instruction analysis."""

    def __init__(self):
        self.extractor = PromptExtractor()
        self.chunker = InstructionChunker()
        self.classifier = IntentClassifier()
        self.detector = OverlapDetector()

    def analyze_file(self, file_path: Path) -> Optional[InstructionGraph]:
        """Analyze a single file for instruction redundancies."""
        # Extract text
        text = self.extractor.extract(file_path)
        if not text or len(text) < 100:
            return None

        # Chunk
        chunks = self.chunker.chunk(text, source_file=file_path.name)
        if not chunks:
            return None

        # Classify
        classified = self.classifier.classify_batch(chunks)

        # Detect overlaps
        redundancies, clusters = self.detector.detect_all(classified)

        # Build summary
        summary = self._build_summary(file_path.name, classified, redundancies, clusters)

        return InstructionGraph(
            source_file=file_path.name,
            chunks=classified,
            redundancies=redundancies,
            clusters=clusters,
            summary=summary,
        )

    def analyze_files(self, file_paths: List[Path]) -> List[InstructionGraph]:
        """Analyze multiple files."""
        results = []
        for fp in file_paths:
            graph = self.analyze_file(fp)
            if graph:
                results.append(graph)
        return results

    def analyze_text(self, text: str, source_name: str = "inline") -> Optional[InstructionGraph]:
        """Analyze raw text content (for inline prompt strings)."""
        if not text or len(text) < 100:
            return None

        chunks = self.chunker.chunk(text, source_file=source_name)
        if not chunks:
            return None

        classified = self.classifier.classify_batch(chunks)
        redundancies, clusters = self.detector.detect_all(classified)
        summary = self._build_summary(source_name, classified, redundancies, clusters)

        return InstructionGraph(
            source_file=source_name,
            chunks=classified,
            redundancies=redundancies,
            clusters=clusters,
            summary=summary,
        )

    def _build_summary(
        self, source_file: str,
        chunks: List[ClassifiedChunk],
        redundancies: List[Redundancy],
        clusters: List[RedundancyCluster],
    ) -> Dict:
        """Build a summary of the analysis."""
        total_chunks = len(chunks)
        total_words = sum(cc.chunk.word_count for cc in chunks)

        # Intent distribution
        intent_counts = {}
        for cc in chunks:
            for intent in cc.intents:
                intent_counts[intent.value] = intent_counts.get(intent.value, 0) + 1

        # Severity distribution
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for cc in chunks:
            severity_counts[cc.severity] = severity_counts.get(cc.severity, 0) + 1

        # Redundancy counts by type
        redundancy_types = {}
        for r in redundancies:
            redundancy_types[r.type] = redundancy_types.get(r.type, 0) + 1

        # Redundancy counts by severity
        redundancy_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for r in redundancies:
            redundancy_severity[r.severity] = redundancy_severity.get(r.severity, 0) + 1

        # Topic coverage
        all_topics = set()
        for cc in chunks:
            all_topics.update(cc.chunk.topics)

        # Most duplicated topics
        topic_chunk_count = {}
        for cc in chunks:
            for topic in cc.chunk.topics:
                topic_chunk_count[topic] = topic_chunk_count.get(topic, 0) + 1

        most_duplicated = sorted(topic_chunk_count.items(), key=lambda x: -x[1])[:5]

        return {
            "source_file": source_file,
            "total_chunks": total_chunks,
            "total_words": total_words,
            "avg_chunk_words": total_words // total_chunks if total_chunks > 0 else 0,
            "intent_distribution": intent_counts,
            "severity_distribution": severity_counts,
            "total_redundancies": len(redundancies),
            "redundancy_types": redundancy_types,
            "redundancy_severity": redundancy_severity,
            "total_clusters": len(clusters),
            "topics_covered": sorted(all_topics),
            "most_duplicated_topics": [
                {"topic": t, "chunk_count": c} for t, c in most_duplicated
            ],
            "redundancy_rate": round(
                len(redundancies) / total_chunks * 100 if total_chunks > 0 else 0, 1
            ),
        }
