"""Git-working-tree canonical store for Apprentice long-term knowledge.

The store writes human-readable Markdown with provenance metadata. It never
runs ``git add`` or ``git commit``: committing/reviewing remains the
responsibility of Apprentice (or a human), preserving an explicit audit gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Optional, Protocol

from .models import CanonicalRecord, CurationCandidate, utc_now_iso


class CanonicalStore(Protocol):
    def find_by_hash(self, sha256: str) -> Optional[CanonicalRecord]: ...
    def persist(self, candidate: CurationCandidate) -> CanonicalRecord: ...


_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_segment(value: str, fallback: str = "memory") -> str:
    value = value.strip().replace(" ", "-")
    if value in {"", ".", ".."}:
        value = fallback
    value = _SAFE_SEGMENT.sub("-", value).strip("-.")
    if not value or value in {".", ".."}:
        return fallback
    return value[:96]


def _safe_namespace(namespace: str) -> Path:
    raw = Path(namespace)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("namespace must be a relative path without '..'")
    parts = [_safe_segment(part) for part in raw.parts if part not in {"", "."}]
    return Path(*parts) if parts else Path("memory")


def _frontmatter_value(value) -> str:
    # JSON scalars/lists are valid YAML and avoid hand-written escaping bugs.
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass
class GitWorkingTreeStore:
    """Canonical knowledge writer rooted at an existing Git working tree."""

    repo_root: Path
    prefix: Path = Path("knowledge/memory")

    def __post_init__(self) -> None:
        self.repo_root = Path(self.repo_root).expanduser().resolve()
        self.prefix = Path(self.prefix)
        if self.prefix.is_absolute() or ".." in self.prefix.parts:
            raise ValueError("prefix must stay inside repo_root")
        if not self.repo_root.exists() or not self.repo_root.is_dir():
            raise ValueError(f"canonical repo does not exist: {self.repo_root}")

    @property
    def canonical_root(self) -> Path:
        target = (self.repo_root / self.prefix).resolve()
        self._assert_inside_repo(target)
        return target

    def _assert_inside_repo(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError("canonical path escapes repo_root") from exc

    def find_by_hash(self, sha256: str) -> Optional[CanonicalRecord]:
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        root = self.canonical_root
        if not root.exists():
            return None
        for path in root.rglob(f"*--{sha256}.md"):
            self._assert_inside_repo(path)
            relative = path.relative_to(self.repo_root).as_posix()
            return CanonicalRecord(
                canonical_id=f"sha256:{sha256}",
                sha256=sha256,
                relative_path=relative,
                promoted_at="",
            )
        return None

    def persist(self, candidate: CurationCandidate) -> CanonicalRecord:
        existing = self.find_by_hash(candidate.sha256)
        if existing is not None:
            return existing

        namespace = _safe_namespace(candidate.namespace)
        title = _safe_segment(candidate.title or "memory")
        destination_dir = (self.canonical_root / namespace).resolve()
        self._assert_inside_repo(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination = destination_dir / f"{title}--{candidate.sha256}.md"
        self._assert_inside_repo(destination)
        promoted_at = utc_now_iso()

        source = candidate.source
        metadata = [
            ("schema", 1),
            ("canonical_id", candidate.canonical_id),
            ("sha256", candidate.sha256),
            ("source_type", source.source_type),
            ("source_id", source.source_id),
            ("source_uri", source.uri or ""),
            ("source_version", source.version or ""),
            ("agent_id", candidate.agent_id),
            ("confidence", candidate.confidence),
            ("sensitivity", candidate.sensitivity),
            ("namespace", candidate.namespace),
            ("created_at", candidate.created_at),
            ("promoted_at", promoted_at),
            ("supersedes", list(candidate.supersedes)),
        ]
        frontmatter = "\n".join(f"{key}: {_frontmatter_value(value)}" for key, value in metadata)
        body = f"---\n{frontmatter}\n---\n\n{candidate.content}\n"

        # Atomic replace in the destination directory. There is deliberately no
        # automatic Git staging/commit here.
        fd, tmp_name = tempfile.mkstemp(prefix=".apprentice-", suffix=".tmp", dir=destination_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, destination)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

        return CanonicalRecord(
            canonical_id=candidate.canonical_id,
            sha256=candidate.sha256,
            relative_path=destination.relative_to(self.repo_root).as_posix(),
            promoted_at=promoted_at,
        )
