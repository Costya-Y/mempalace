"""Policy gate between MemPalace working memory and Apprentice canonical Git knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .models import ConflictResult, CurationCandidate, CurationResult, Decision
from .store import CanonicalStore


class ConflictDetector(Protocol):
    """Optional semantic/graph-aware conflict detector."""

    def detect(self, candidate: CurationCandidate) -> ConflictResult: ...


class NoopConflictDetector:
    def detect(self, candidate: CurationCandidate) -> ConflictResult:
        return ConflictResult()


@dataclass(frozen=True)
class CuratorPolicy:
    min_confidence: float = 0.75
    require_provenance: bool = True
    allowed_sensitivities: tuple[str, ...] = ("normal",)
    require_agent_id: bool = True
    explicit_promotion: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")


class MemoryCurator:
    def __init__(
        self,
        store: CanonicalStore,
        policy: Optional[CuratorPolicy] = None,
        conflict_detector: Optional[ConflictDetector] = None,
    ) -> None:
        self.store = store
        self.policy = policy or CuratorPolicy()
        self.conflict_detector = conflict_detector or NoopConflictDetector()

    def curate(self, candidate: CurationCandidate) -> CurationResult:
        sha = candidate.sha256
        if not candidate.content.strip():
            return CurationResult(Decision.REJECT, sha, "empty content")
        if not 0.0 <= candidate.confidence <= 1.0:
            return CurationResult(Decision.REJECT, sha, "confidence must be between 0 and 1")
        if self.policy.require_provenance and not candidate.source.is_complete():
            return CurationResult(Decision.HOLD, sha, "provenance is incomplete")
        if self.policy.require_agent_id and not candidate.agent_id.strip():
            return CurationResult(Decision.HOLD, sha, "agent_id is required")
        if candidate.confidence < self.policy.min_confidence:
            return CurationResult(
                Decision.HOLD,
                sha,
                f"confidence {candidate.confidence:.3f} is below {self.policy.min_confidence:.3f}",
            )
        if candidate.sensitivity not in self.policy.allowed_sensitivities:
            return CurationResult(
                Decision.HOLD,
                sha,
                f"sensitivity '{candidate.sensitivity}' requires separate approval",
            )

        existing = self.store.find_by_hash(sha)
        if existing is not None:
            return CurationResult(
                Decision.REJECT,
                sha,
                "exact content already exists in canonical knowledge",
                canonical_ref=existing.relative_path,
            )

        conflict = self.conflict_detector.detect(candidate)
        if conflict.conflict:
            return CurationResult(
                Decision.HOLD,
                sha,
                conflict.reason or "candidate conflicts with canonical knowledge",
                conflict_references=conflict.references,
            )

        return CurationResult(
            Decision.PROMOTE,
            sha,
            "eligible for canonical promotion",
            requires_explicit_promotion=self.policy.explicit_promotion,
        )
