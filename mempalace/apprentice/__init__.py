"""Apprentice canonical-memory integration for MemPalace.

MemPalace remains working memory; this package provides the explicit promotion
boundary into an auditable Git-backed long-term knowledge store.
"""

from .curator import CuratorPolicy, MemoryCurator, NoopConflictDetector
from .models import (
    CanonicalRecord,
    ConflictResult,
    CurationCandidate,
    CurationResult,
    Decision,
    SourceRef,
    content_sha256,
)
from .service import ApprenticeSettings, CanonicalMemoryService, make_candidate
from .store import CanonicalStore, GitWorkingTreeStore

__all__ = [
    "ApprenticeSettings",
    "CanonicalMemoryService",
    "CanonicalRecord",
    "CanonicalStore",
    "ConflictResult",
    "CurationCandidate",
    "CurationResult",
    "CuratorPolicy",
    "Decision",
    "GitWorkingTreeStore",
    "MemoryCurator",
    "NoopConflictDetector",
    "SourceRef",
    "content_sha256",
    "make_candidate",
]
