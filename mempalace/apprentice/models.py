"""Data model for Apprentice canonical-memory curation.

This module is intentionally dependency-free. MemPalace remains the working
memory/retrieval layer; these objects describe candidates crossing the boundary
into an audited Git-backed canonical knowledge store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def content_sha256(content: str) -> str:
    """Stable digest of the exact UTF-8 content being considered for promotion."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Decision(str, Enum):
    PROMOTE = "promote"
    HOLD = "hold"
    REJECT = "reject"


@dataclass(frozen=True)
class SourceRef:
    """Provenance for a memory candidate."""

    source_type: str
    source_id: str
    uri: Optional[str] = None
    version: Optional[str] = None

    def is_complete(self) -> bool:
        return bool(self.source_type.strip() and self.source_id.strip())


@dataclass(frozen=True)
class CurationCandidate:
    """A verbatim memory proposed for canonical promotion."""

    content: str
    source: SourceRef
    agent_id: str
    confidence: float = 1.0
    sensitivity: str = "normal"
    namespace: str = "memory"
    title: Optional[str] = None
    supersedes: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now_iso)

    @property
    def sha256(self) -> str:
        return content_sha256(self.content)

    @property
    def canonical_id(self) -> str:
        return f"sha256:{self.sha256}"


@dataclass(frozen=True)
class ConflictResult:
    conflict: bool = False
    reason: str = ""
    references: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CurationResult:
    decision: Decision
    candidate_sha256: str
    reason: str
    requires_explicit_promotion: bool = True
    canonical_ref: Optional[str] = None
    conflict_references: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "candidate_sha256": self.candidate_sha256,
            "reason": self.reason,
            "requires_explicit_promotion": self.requires_explicit_promotion,
            "canonical_ref": self.canonical_ref,
            "conflict_references": list(self.conflict_references),
        }


@dataclass(frozen=True)
class CanonicalRecord:
    canonical_id: str
    sha256: str
    relative_path: str
    promoted_at: str

    def to_dict(self) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "sha256": self.sha256,
            "relative_path": self.relative_path,
            "promoted_at": self.promoted_at,
        }
