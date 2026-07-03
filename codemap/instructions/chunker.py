"""Semantic Chunker — Split instruction text into meaningful, classified chunks.

Instead of naively splitting by lines or paragraphs, this chunker:
1. Splits by markdown headers (##, ###, ####)
2. Splits by horizontal rules (---) or blank lines between sections
3. Groups related lines (bullet points under a heading)
4. Preserves code blocks as atomic units
5. Extracts inline code references (question IDs, function names)
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class InstructionChunk:
    """A semantically meaningful chunk of instruction text."""
    id: str
    text: str
    line_start: int
    line_end: int
    heading: str  # Nearest heading above this chunk
    heading_level: int  # 1-6 for # through ######
    topics: Set[str] = field(default_factory=set)
    question_ids: Set[str] = field(default_factory=set)
    scope_tags: Set[str] = field(default_factory=set)
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split())


class InstructionChunker:
    """Split instruction text into semantic chunks."""

    # Patterns for detecting section boundaries
    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
    HR_PATTERN = re.compile(r"^---+$", re.MULTILINE)
    BULLET_PATTERN = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")

    # Topic keyword patterns (case-insensitive)
    TOPIC_PATTERNS = {
        "education": re.compile(r"\b(education|degree|diploma|university|school|academic|credential|enrollment|graduation)\b", re.IGNORECASE),
        "career": re.compile(r"\b(career|employment|job|profession|work|employer|occupation|seniority|experience)\b", re.IGNORECASE),
        "language": re.compile(r"\b(language|english|ielts|toefl|pte|proficiency|linguistic|native|fluent)\b", re.IGNORECASE),
        "financial": re.compile(r"\b(financial|savings|income|salary|revenue|budget|cost|funds|money|wealth|afford)\b", re.IGNORECASE),
        "visa": re.compile(r"\b(visa|permit|status|immigration|migrant|passport|border|entry|overstay)\b", re.IGNORECASE),
        "family": re.compile(r"\b(family|spouse|partner|children|dependents|parent|marital|household)\b", re.IGNORECASE),
        "pathway": re.compile(r"\b(pathway|route|stream|program|category|eligibility|qualification)\b", re.IGNORECASE),
        "timeline": re.compile(r"\b(timeline|deadline|processing|wait|duration|timeframe|schedule)\b", re.IGNORECASE),
        "document": re.compile(r"\b(document|paperwork|certificate|transcript|assessment|evaluation|认证)\b", re.IGNORECASE),
        "sovereignty": re.compile(r"\b(sovereignty|independence|autonomy|self.sufficient|diversif)\b", re.IGNORECASE),
        "archetype": re.compile(r"\b(archetype|dreamer|planner|survivor|builder|paper.chaser)\b", re.IGNORECASE),
        "inquiry": re.compile(r"\b(ask|assume|inquir|question|probe|never.*skip|always.*ask|don.t.*assume)\b", re.IGNORECASE),
        "risk": re.compile(r"\b(risk|danger|barrier|impossib|refusal|denial|criminal|inadmiss)\b", re.IGNORECASE),
        "settlement": re.compile(r"\b(settl|integrat|adapt|community|social|network|diaspora)\b", re.IGNORECASE),
        "citizenship": re.compile(r"\b(citizen|naturaliz|passport|national)\b", re.IGNORECASE),
    }

    # Question ID pattern (q_xxx, q_xxx_yyy, etc.)
    QUESTION_ID_PATTERN = re.compile(r"\b(q_[a-z][a-z0-9_]*)\b")

    # Scope keywords
    SCOPE_KEYWORDS = {
        "pre_immigration": re.compile(r"\b(pre.immigration|exploring|planning|ready)\b", re.IGNORECASE),
        "in_process": re.compile(r"\b(in.process|applied|waiting|application)\b", re.IGNORECASE),
        "post_immigration": re.compile(r"\b(post.immigration|settled|permanent.resident|citizen|living.abroad)\b", re.IGNORECASE),
        "global": re.compile(r"\b(always|never|critical|mandatory|required|universal)\b", re.IGNORECASE),
        "turn_specific": re.compile(r"\b(turn\s*\d|turn\s*\d+[-+])\b", re.IGNORECASE),
    }

    def chunk(self, text: str, source_file: str = "") -> List[InstructionChunk]:
        """Split instruction text into semantic chunks.

        Strategy:
        1. Find all header positions as primary split points
        2. Within each section, find sub-splits at HR rules or blank line groups
        3. Group bullet points with their parent heading
        4. Preserve code blocks as atomic units
        """
        lines = text.split("\n")
        chunks = []

        # Find header positions
        headers = []
        for i, line in enumerate(lines):
            match = self.HEADER_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                headers.append((i, level, title))

        # If no headers, treat the whole file as one chunk
        if not headers:
            chunk = self._make_chunk(
                text=text,
                source_file=source_file,
                line_start=1,
                line_end=len(lines),
                heading="(root)",
                heading_level=0,
                chunk_index=0,
            )
            return [chunk] if chunk.text.strip() else []

        # Split into sections based on headers
        sections = []
        for idx, (line_num, level, title) in enumerate(headers):
            # Section ends at next header of same or higher level, or EOF
            end_line = len(lines)
            for next_line, next_level, _ in headers[idx + 1:]:
                if next_level <= level:
                    end_line = next_line
                    break

            section_text = "\n".join(lines[line_num:end_line]).strip()
            sections.append((line_num, level, title, section_text, end_line))

        # Within each section, check for sub-splits
        chunk_index = 0
        for line_num, level, title, section_text, end_line in sections:
            sub_chunks = self._split_section(section_text, line_num, source_file, title, level, chunk_index)
            chunks.extend(sub_chunks)
            chunk_index += len(sub_chunks)

        return chunks

    def _split_section(
        self, text: str, base_line: int, source_file: str,
        heading: str, heading_level: int, start_index: int,
    ) -> List[InstructionChunk]:
        """Split a section into sub-chunks if it's long enough."""
        lines = text.split("\n")

        # If section is short, keep as one chunk
        if len(lines) <= 15 or len(text.split()) <= 80:
            chunk = self._make_chunk(
                text=text,
                source_file=source_file,
                line_start=base_line + 1,
                line_end=base_line + len(lines),
                heading=heading,
                heading_level=heading_level,
                chunk_index=start_index,
            )
            return [chunk] if chunk.text.strip() else []

        # Split at HR rules or double blank lines
        sub_chunks = []
        current_lines = []
        current_start = base_line

        for i, line in enumerate(lines):
            if self.HR_PATTERN.match(line.strip()) or (not line.strip() and i > 0 and not lines[i - 1].strip()):
                if current_lines:
                    sub_text = "\n".join(current_lines).strip()
                    if len(sub_text.split()) > 20:  # Only keep meaningful sub-chunks
                        chunk = self._make_chunk(
                            text=sub_text,
                            source_file=source_file,
                            line_start=current_start + 1,
                            line_end=base_line + i,
                            heading=heading,
                            heading_level=heading_level,
                            chunk_index=start_index + len(sub_chunks),
                        )
                        if chunk.text.strip():
                            sub_chunks.append(chunk)
                    current_lines = []
                    current_start = base_line + i + 1
                else:
                    current_start = base_line + i + 1
            else:
                current_lines.append(line)

        # Don't forget the last sub-chunk
        if current_lines:
            sub_text = "\n".join(current_lines).strip()
            if len(sub_text.split()) > 20:
                chunk = self._make_chunk(
                    text=sub_text,
                    source_file=source_file,
                    line_start=current_start + 1,
                    line_end=base_line + len(lines),
                    heading=heading,
                    heading_level=heading_level,
                    chunk_index=start_index + len(sub_chunks),
                )
                if chunk.text.strip():
                    sub_chunks.append(chunk)

        # If we couldn't split meaningfully, return as one chunk
        if not sub_chunks:
            chunk = self._make_chunk(
                text=text,
                source_file=source_file,
                line_start=base_line + 1,
                line_end=base_line + len(lines),
                heading=heading,
                heading_level=heading_level,
                chunk_index=start_index,
            )
            return [chunk] if chunk.text.strip() else []

        return sub_chunks

    def _make_chunk(
        self, text: str, source_file: str, line_start: int, line_end: int,
        heading: str, heading_level: int, chunk_index: int,
    ) -> InstructionChunk:
        """Create an InstructionChunk with extracted metadata."""
        chunk_id = f"{source_file}:chunk_{chunk_index}" if source_file else f"chunk_{chunk_index}"

        # Extract question IDs
        question_ids = set(self.QUESTION_ID_PATTERN.findall(text))

        # Extract topics
        topics = set()
        for topic, pattern in self.TOPIC_PATTERNS.items():
            if pattern.search(text):
                topics.add(topic)

        # Extract scope tags
        scope_tags = set()
        for scope, pattern in self.SCOPE_KEYWORDS.items():
            if pattern.search(text):
                scope_tags.add(scope)

        return InstructionChunk(
            id=chunk_id,
            text=text.strip(),
            line_start=line_start,
            line_end=line_end,
            heading=heading,
            heading_level=heading_level,
            topics=topics,
            question_ids=question_ids,
            scope_tags=scope_tags,
        )
