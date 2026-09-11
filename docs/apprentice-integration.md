# Apprentice + MemPalace memory architecture

This integration separates **working memory** from **canonical long-term knowledge**.

- **MemPalace** is the working-memory, semantic-retrieval, diary, graph, and MCP layer.
- **Apprentice Git knowledge** is the authoritative, auditable long-term record.
- **Memory Curator** is the policy boundary between them.
- Vector/graph indexes are treated as derived state; they must not silently redefine canonical truth.

## Architecture

```text
Coordinator / Developer / Research / Ops agents
                    |
                    | MCP
                    v
            +----------------+
            |   MemPalace    |
            | working memory |
            | semantic recall|
            | diary + graph  |
            +-------+--------+
                    |
              candidate memory
                    |
                    v
            +----------------+
            | Memory Curator |
            | provenance     |
            | confidence     |
            | sensitivity    |
            | duplicates     |
            | conflict hook  |
            +-------+--------+
                    |
          explicit reviewed promotion
                    |
                    v
            +----------------+
            | Apprentice Git |
            | canonical KB   |
            | Markdown       |
            | history/review |
            +----------------+
```

## Invariants

1. Ordinary MemPalace writes do **not** become canonical knowledge automatically.
2. `curate` is side-effect free.
3. Canonical promotion is a separate explicit operation.
4. Approval is bound to the exact verbatim content through SHA-256.
5. Every canonical record carries provenance, agent identity, confidence, sensitivity, timestamps, and supersession references.
6. Exact canonical duplicates are rejected.
7. Low-confidence, incomplete-provenance, sensitive, or detected-conflict candidates are held for review.
8. The canonical store writes into a Git working tree but never stages or commits automatically.
9. Models and agents are replaceable; identity and durable knowledge live outside model weights.

## Configuration

The integration is opt-in and disabled by default.

```bash
export MEMPALACE_APPRENTICE_ENABLED=true
export MEMPALACE_APPRENTICE_REPO=/path/to/apprentice
export MEMPALACE_APPRENTICE_PREFIX=knowledge/memory
export MEMPALACE_APPRENTICE_MIN_CONFIDENCE=0.75
```

`MEMPALACE_APPRENTICE_REPO` should point at the Apprentice Git working tree. The prefix is always resolved inside that root and path traversal is rejected.

## MCP workflow

Three MCP tools are added without changing the behavior of existing MemPalace tools:

### `mempalace_apprentice_status`

Shows whether the boundary is enabled, its Git root/prefix, confidence threshold, and confirms that automatic Git commits are disabled.

### `mempalace_apprentice_curate`

Evaluates a candidate without writing canonical state. Required fields:

```json
{
  "content": "Use MemPalace as working memory; Git is canonical.",
  "source_type": "drawer",
  "source_id": "drawer-123",
  "agent_id": "coordinator",
  "confidence": 0.98,
  "namespace": "decisions/architecture",
  "title": "memory-authority"
}
```

A promotable response contains the SHA-256 of the exact content. `hold` means human/agent review is required; `reject` means the candidate is unsuitable or already canonical.

### `mempalace_apprentice_promote`

Requires the same candidate plus `expected_sha256`. The service recomputes the hash and re-runs curation immediately before the write. This prevents approval of one text from being reused for modified text.

Promotion writes Markdown into the configured Apprentice working tree and returns its relative path. It does **not** run `git add` or `git commit`.

## Canonical record

Canonical records are human-readable Markdown with YAML-compatible front matter:

```markdown
---
schema: 1
canonical_id: "sha256:..."
sha256: "..."
source_type: "conversation"
source_id: "session-1"
source_uri: "chat://session-1"
source_version: "turn-7"
agent_id: "coordinator"
confidence: 0.98
sensitivity: "normal"
namespace: "decisions/architecture"
created_at: "..."
promoted_at: "..."
supersedes: []
---

Use MemPalace as working memory; Git is canonical.
```

The body remains verbatim. Filenames include the full content hash, making canonical references content-addressable while retaining a readable title and namespace.

## Curation policy

The deterministic baseline currently implements:

- exact canonical duplicate detection by content hash;
- required provenance (`source_type` + `source_id`);
- required proposing agent identity;
- configurable minimum confidence;
- sensitivity gate (only `normal` is auto-eligible by default);
- explicit `supersedes` provenance for replacement knowledge;
- a pluggable `ConflictDetector` interface.

The default conflict detector is deliberately a no-op. It is safer to expose a defined extension point than to pretend that lexical heuristics can reliably identify semantic contradictions. Apprentice can inject a graph/LLM-aware detector later; any detected conflict produces `hold`, never automatic replacement.

## Relationship to existing MemPalace behavior

Existing `mempalace_add_drawer`, checkpoint, diary, knowledge-graph, and semantic duplicate behavior remains unchanged. A normal memory first lives in MemPalace. Only selected durable knowledge crosses the curator boundary.

This keeps the roles distinct:

| Concern | Owner |
|---|---|
| Fast semantic recall | MemPalace |
| Agent diary / episodic memory | MemPalace |
| Knowledge graph / relationships | MemPalace |
| Working-memory dedup | MemPalace |
| Canonical authority | Apprentice Git |
| Audit/diff/rollback | Git |
| Promotion policy | Memory Curator |
| Semantic contradiction detector | Pluggable curator extension |
| Git commit/review | Apprentice coordinator or human |

## Deliberately not automatic

The first integration does not automatically commit Git, rewrite old canonical records, auto-promote every drawer, or let an LLM resolve contradictions by itself. Those are authority-changing actions and belong behind explicit policy/review boundaries.
