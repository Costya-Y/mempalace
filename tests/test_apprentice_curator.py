from pathlib import Path

import pytest

from mempalace.apprentice import (
    CanonicalMemoryService,
    ConflictResult,
    CurationCandidate,
    CuratorPolicy,
    Decision,
    GitWorkingTreeStore,
    MemoryCurator,
    SourceRef,
    content_sha256,
)


def candidate(content="Keep this", **kwargs):
    defaults = dict(
        source=SourceRef("conversation", "session-1", "chat://session-1", "turn-7"),
        agent_id="coordinator",
        confidence=0.95,
        sensitivity="normal",
        namespace="decisions/architecture",
        title="memory-boundary",
    )
    defaults.update(kwargs)
    return CurationCandidate(content=content, **defaults)


def service(tmp_path: Path, min_confidence=0.75, conflict_detector=None):
    store = GitWorkingTreeStore(tmp_path)
    curator = MemoryCurator(
        store,
        CuratorPolicy(min_confidence=min_confidence),
        conflict_detector=conflict_detector,
    )
    return CanonicalMemoryService(curator)


def test_content_hash_is_stable():
    assert content_sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_curate_is_side_effect_free_and_promote_writes_markdown(tmp_path):
    svc = service(tmp_path)
    item = candidate()
    decision = svc.curate(item)
    assert decision.decision is Decision.PROMOTE
    assert list(tmp_path.rglob("*.md")) == []

    record = svc.promote(item, expected_sha256=item.sha256)
    path = tmp_path / record.relative_path
    text = path.read_text(encoding="utf-8")
    assert item.content in text
    assert item.sha256 in text
    assert 'source_id: "session-1"' in text
    assert 'agent_id: "coordinator"' in text


def test_exact_duplicate_is_rejected_after_promotion(tmp_path):
    svc = service(tmp_path)
    item = candidate()
    svc.promote(item, expected_sha256=item.sha256)
    decision = svc.curate(item)
    assert decision.decision is Decision.REJECT
    assert decision.canonical_ref


def test_low_confidence_and_sensitive_content_are_held(tmp_path):
    svc = service(tmp_path)
    assert svc.curate(candidate(confidence=0.2)).decision is Decision.HOLD
    assert svc.curate(candidate(sensitivity="sensitive")).decision is Decision.HOLD


def test_missing_provenance_is_held(tmp_path):
    svc = service(tmp_path)
    item = candidate(source=SourceRef("", ""))
    assert svc.curate(item).decision is Decision.HOLD


def test_expected_hash_binds_explicit_approval(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(ValueError, match="expected_sha256"):
        svc.promote(candidate(), expected_sha256="0" * 64)


def test_namespace_cannot_escape_repo(tmp_path):
    svc = service(tmp_path)
    item = candidate(namespace="../../outside")
    with pytest.raises(ValueError, match="relative path"):
        svc.promote(item, expected_sha256=item.sha256)


def test_conflict_detector_can_hold_candidate(tmp_path):
    class Detector:
        def detect(self, item):
            return ConflictResult(True, "contradicts canonical decision", ("decision:old",))

    svc = service(tmp_path, conflict_detector=Detector())
    result = svc.curate(candidate())
    assert result.decision is Decision.HOLD
    assert result.conflict_references == ("decision:old",)
