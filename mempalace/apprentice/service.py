"""Orchestration and opt-in environment configuration for Apprentice integration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Optional

from .curator import CuratorPolicy, MemoryCurator
from .models import CanonicalRecord, CurationCandidate, CurationResult, Decision, SourceRef
from .store import GitWorkingTreeStore


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ApprenticeSettings:
    enabled: bool = False
    repo_root: Optional[Path] = None
    prefix: Path = Path("knowledge/memory")
    min_confidence: float = 0.75

    @classmethod
    def from_env(cls) -> "ApprenticeSettings":
        root = os.getenv("MEMPALACE_APPRENTICE_REPO")
        return cls(
            enabled=_env_bool("MEMPALACE_APPRENTICE_ENABLED", False),
            repo_root=Path(root).expanduser() if root else None,
            prefix=Path(os.getenv("MEMPALACE_APPRENTICE_PREFIX", "knowledge/memory")),
            min_confidence=float(os.getenv("MEMPALACE_APPRENTICE_MIN_CONFIDENCE", "0.75")),
        )

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "repo_root": str(self.repo_root) if self.repo_root else None,
            "prefix": self.prefix.as_posix(),
            "min_confidence": self.min_confidence,
            "auto_commit": False,
            "authority": "git_working_tree",
            "mempalace_role": "working_memory_and_retrieval",
        }

    def build_service(self) -> "CanonicalMemoryService":
        if not self.enabled:
            raise RuntimeError("Apprentice canonical memory is disabled")
        if self.repo_root is None:
            raise RuntimeError("MEMPALACE_APPRENTICE_REPO is required when integration is enabled")
        store = GitWorkingTreeStore(self.repo_root, self.prefix)
        curator = MemoryCurator(store, CuratorPolicy(min_confidence=self.min_confidence))
        return CanonicalMemoryService(curator)


class CanonicalMemoryService:
    """Two-step curate/promote boundary.

    ``curate`` is side-effect free. ``promote`` re-runs curation immediately
    before writing, so policy/duplicate state cannot be bypassed by a stale
    earlier decision. A caller may provide ``expected_sha256`` to bind explicit
    approval to the exact verbatim content that was reviewed.
    """

    def __init__(self, curator: MemoryCurator) -> None:
        self.curator = curator

    def curate(self, candidate: CurationCandidate) -> CurationResult:
        return self.curator.curate(candidate)

    def promote(self, candidate: CurationCandidate, *, expected_sha256: Optional[str] = None) -> CanonicalRecord:
        if expected_sha256 is not None and expected_sha256 != candidate.sha256:
            raise ValueError("expected_sha256 does not match the candidate content")
        decision = self.curator.curate(candidate)
        if decision.decision is not Decision.PROMOTE:
            raise ValueError(f"candidate is not promotable: {decision.reason}")
        return self.curator.store.persist(candidate)


def make_candidate(
    *,
    content: str,
    source_type: str,
    source_id: str,
    agent_id: str,
    confidence: float = 1.0,
    sensitivity: str = "normal",
    namespace: str = "memory",
    title: Optional[str] = None,
    source_uri: Optional[str] = None,
    source_version: Optional[str] = None,
    supersedes: Optional[Iterable[str]] = None,
) -> CurationCandidate:
    return CurationCandidate(
        content=content,
        source=SourceRef(source_type, source_id, source_uri, source_version),
        agent_id=agent_id,
        confidence=confidence,
        sensitivity=sensitivity,
        namespace=namespace,
        title=title,
        supersedes=tuple(supersedes or ()),
    )
