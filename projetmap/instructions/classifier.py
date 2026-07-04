"""Intent Classifier — Classify instruction chunks by their purpose.

Each chunk gets classified into one or more intent types:
- CONSTRAINT: Prohibits or restricts behavior (NEVER, DO NOT, MUST NOT)
- MANDATE: Requires or enforces behavior (ALWAYS, MUST, REQUIRED)
- WORKFLOW: Describes sequence of actions (Turn 1, then Turn 2, ...)
- DEFINITION: Defines a concept, type, or schema
- EXAMPLE: Provides illustrative examples (GOOD:, BAD:, Example:)
- SCOPE: Limits applicability to specific contexts (for settled users, when X...)
- QUESTION: Poses a question or decision point
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from .chunker import InstructionChunk


class IntentType(str, Enum):
    CONSTRAINT = "constraint"
    MANDATE = "mandate"
    WORKFLOW = "workflow"
    DEFINITION = "definition"
    EXAMPLE = "example"
    SCOPE = "scope"
    QUESTION = "question"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedChunk:
    """An InstructionChunk with its classified intent."""
    chunk: InstructionChunk
    intents: set[IntentType] = field(default_factory=set)
    primary_intent: IntentType = IntentType.UNKNOWN
    confidence: float = 0.0
    severity: str = "medium"  # low, medium, high, critical


class IntentClassifier:
    """Classify instruction chunks by intent type."""

    # Pattern groups for each intent type
    CONSTRAINT_PATTERNS = [
        re.compile(r"\bNEVER\b", re.IGNORECASE),
        re.compile(r"\bDO NOT\b", re.IGNORECASE),
        re.compile(r"\bMUST NOT\b", re.IGNORECASE),
        re.compile(r"\bSHALL NOT\b", re.IGNORECASE),
        re.compile(r"\bAVOID\b", re.IGNORECASE),
        re.compile(r"\bSKIP\b", re.IGNORECASE),
        re.compile(r"\bPROHIBITED\b", re.IGNORECASE),
        re.compile(r"\bDON'?T\b", re.IGNORECASE),
        re.compile(r"\bNOT.*ALLOWED\b", re.IGNORECASE),
        re.compile(r"\bNEVER SKIP\b", re.IGNORECASE),
        re.compile(r"\bNEVER REPEAT\b", re.IGNORECASE),
        re.compile(r"\bNEVER ASSUME\b", re.IGNORECASE),
    ]

    MANDATE_PATTERNS = [
        re.compile(r"\bALWAYS\b", re.IGNORECASE),
        re.compile(r"\bMUST\b", re.IGNORECASE),
        re.compile(r"\bREQUIRED\b", re.IGNORECASE),
        re.compile(r"\bMANDATORY\b", re.IGNORECASE),
        re.compile(r"\bSHALL\b", re.IGNORECASE),
        re.compile(r"\bNEED TO\b", re.IGNORECASE),
        re.compile(r"\bIMPORTANT\b", re.IGNORECASE),
        re.compile(r"\bCRITICAL\b", re.IGNORECASE),
        re.compile(r"\bALWAYS ASK\b", re.IGNORECASE),
        re.compile(r"\bALWAYS INCLUDE\b", re.IGNORECASE),
        re.compile(r"\bHARD RULE\b", re.IGNORECASE),
        re.compile(r"\bNEVER.*SKIP\b", re.IGNORECASE),
    ]

    WORKFLOW_PATTERNS = [
        re.compile(r"\bturn\s*\d", re.IGNORECASE),
        re.compile(r"\bturn\s*\d+[-+]", re.IGNORECASE),
        re.compile(r"\bstep\s*\d", re.IGNORECASE),
        re.compile(r"\bphase\s*\d", re.IGNORECASE),
        re.compile(r"\bthen\b", re.IGNORECASE),
        re.compile(r"\bfollowed by\b", re.IGNORECASE),
        re.compile(r"\bafter.*(?:answer|response|reply)", re.IGNORECASE),
        re.compile(r"\bbefore.*(?:proceed|continue|move)", re.IGNORECASE),
        re.compile(r"\bflow\b", re.IGNORECASE),
        re.compile(r"\bsequence\b", re.IGNORECASE),
        re.compile(r"\border\b", re.IGNORECASE),
        re.compile(r"\bfirs(t|tly)\b", re.IGNORECASE),
        re.compile(r"\bnext\b", re.IGNORECASE),
        re.compile(r"\bfinally\b", re.IGNORECASE),
    ]

    DEFINITION_PATTERNS = [
        re.compile(r"\bis defined as\b", re.IGNORECASE),
        re.compile(r"\bmeans\b", re.IGNORECASE),
        re.compile(r"\brefers to\b", re.IGNORECASE),
        re.compile(r"\bconsists of\b", re.IGNORECASE),
        re.compile(r"\bincludes\b", re.IGNORECASE),
        re.compile(r"\bhas the following\b", re.IGNORECASE),
        re.compile(r"\btypes?:?\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"\bmodel\b", re.IGNORECASE),
        re.compile(r"\bschema\b", re.IGNORECASE),
        re.compile(r"\bfield\b", re.IGNORECASE),
        re.compile(r"\benum\b", re.IGNORECASE),
        re.compile(r"\bvalue\b", re.IGNORECASE),
        re.compile(r"```json", re.IGNORECASE),
        re.compile(r"```dart", re.IGNORECASE),
    ]

    EXAMPLE_PATTERNS = [
        re.compile(r"\bexample\b", re.IGNORECASE),
        re.compile(r"\bGOOD:\s", re.IGNORECASE),
        re.compile(r"\bBAD:\s", re.IGNORECASE),
        re.compile(r"\bVIOLATION\b", re.IGNORECASE),
        re.compile(r"\binstead of\b", re.IGNORECASE),
        re.compile(r"\be\.g\.\b", re.IGNORECASE),
        re.compile(r"\bsuch as\b", re.IGNORECASE),
        re.compile(r"\bfor instance\b", re.IGNORECASE),
        re.compile(r"```", re.MULTILINE),  # Code blocks are often examples
    ]

    SCOPE_PATTERNS = [
        re.compile(r"\bfor\s+(pre|post|in|settled|exploring|planning|ready)\b", re.IGNORECASE),
        re.compile(r"\bwhen\s+(?:the\s+)?(?:user|lifecycle|status)", re.IGNORECASE),
        re.compile(r"\bif\s+(?:the\s+)?(?:user|lifecycle|pathway)", re.IGNORECASE),
        re.compile(r"\b(pre-immigration|in-process|post-immigration|settled)\b", re.IGNORECASE),
        re.compile(r"\b(pre_immigration|in_process|post_immigration|settled_pr)\b", re.IGNORECASE),
        re.compile(r"\b(adapt to lifecycle)\b", re.IGNORECASE),
        re.compile(r"\b(lifecycle-based|context-aware|contextual)\b", re.IGNORECASE),
    ]

    QUESTION_PATTERNS = [
        re.compile(r"^\s*\?\s*$", re.MULTILINE),
        re.compile(r"\bask\s+['\"]", re.IGNORECASE),
        re.compile(r"\bquestion\b", re.IGNORECASE),
        re.compile(r"\binquire\b", re.IGNORECASE),
        re.compile(r"\bprobe\b", re.IGNORECASE),
    ]

    def classify(self, chunk: InstructionChunk) -> ClassifiedChunk:
        """Classify a chunk's intent(s)."""
        text = chunk.text
        intents = set()
        scores = {}

        # Check each intent type
        for intent_type, patterns in [
            (IntentType.CONSTRAINT, self.CONSTRAINT_PATTERNS),
            (IntentType.MANDATE, self.MANDATE_PATTERNS),
            (IntentType.WORKFLOW, self.WORKFLOW_PATTERNS),
            (IntentType.DEFINITION, self.DEFINITION_PATTERNS),
            (IntentType.EXAMPLE, self.EXAMPLE_PATTERNS),
            (IntentType.SCOPE, self.SCOPE_PATTERNS),
            (IntentType.QUESTION, self.QUESTION_PATTERNS),
        ]:
            matches = sum(1 for p in patterns if p.search(text))
            if matches > 0:
                intents.add(intent_type)
                scores[intent_type] = matches

        # Determine primary intent (highest score)
        if not intents:
            primary = IntentType.UNKNOWN
            confidence = 0.0
        else:
            primary = max(scores, key=scores.get)
            total = sum(scores.values())
            confidence = scores[primary] / total if total > 0 else 0.0

        # Determine severity
        severity = self._determine_severity(text, intents, primary)

        return ClassifiedChunk(
            chunk=chunk,
            intents=intents,
            primary_intent=primary,
            confidence=confidence,
            severity=severity,
        )

    def classify_batch(self, chunks: list[InstructionChunk]) -> list[ClassifiedChunk]:
        """Classify a batch of chunks."""
        return [self.classify(chunk) for chunk in chunks]

    def _determine_severity(
        self, text: str, intents: set[IntentType], primary: IntentType,
    ) -> str:
        """Determine severity based on intent combination and content."""
        # Critical: Constraint + Mandate in same chunk = potential contradiction
        if IntentType.CONSTRAINT in intents and IntentType.MANDATE in intents:
            return "critical"

        # High: Pure constraint or mandate about core topics
        if primary == IntentType.CONSTRAINT:
            # Constraints about "never skip" or "always ask" are high
            if re.search(r"\b(never skip|always ask|never assume)\b", text, re.IGNORECASE):
                return "high"
            return "medium"

        if primary == IntentType.MANDATE:
            # Mandates about core topics are high
            if re.search(r"\b(must ask|required|mandatory)\b", text, re.IGNORECASE):
                return "high"
            return "medium"

        # Workflow is usually medium
        if primary == IntentType.WORKFLOW:
            return "medium"

        # Definition is usually low
        if primary == IntentType.DEFINITION:
            return "low"

        # Example is usually low
        if primary == IntentType.EXAMPLE:
            return "low"

        return "medium"
