# Loaded into mempalace.mcp_server via exec (see __init__.py). Not a standalone module.
if __name__ != "mempalace.mcp_server":
    raise ImportError(f"{__name__} is an implementation fragment; import mempalace.mcp_server")

from ..apprentice import ApprenticeSettings, make_candidate


def _apprentice_settings():
    return ApprenticeSettings.from_env()


def tool_apprentice_status():
    try:
        settings = _apprentice_settings()
        status = settings.status()
        if settings.enabled and settings.repo_root is not None:
            status["repo_exists"] = settings.repo_root.expanduser().exists()
        return {"success": True, **status}
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"success": False, "error": str(exc)}


def _apprentice_candidate(
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
    supersedes: Optional[list] = None,
):
    return make_candidate(
        content=content,
        source_type=source_type,
        source_id=source_id,
        agent_id=agent_id,
        confidence=confidence,
        sensitivity=sensitivity,
        namespace=namespace,
        title=title,
        source_uri=source_uri,
        source_version=source_version,
        supersedes=supersedes,
    )


def tool_apprentice_curate(**kwargs):
    try:
        service = _apprentice_settings().build_service()
        candidate = _apprentice_candidate(**kwargs)
        result = service.curate(candidate)
        return {"success": True, **result.to_dict()}
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"success": False, "error": str(exc)}


def tool_apprentice_promote(expected_sha256: str, **kwargs):
    try:
        service = _apprentice_settings().build_service()
        candidate = _apprentice_candidate(**kwargs)
        record = service.promote(candidate, expected_sha256=expected_sha256)
        return {
            "success": True,
            **record.to_dict(),
            "git_committed": False,
            "next_step": "review and commit the canonical Markdown in the Apprentice repository",
        }
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"success": False, "error": str(exc)}


_CANDIDATE_PROPERTIES = {
    "content": {"type": "string", "description": "Exact verbatim content proposed for canonical knowledge"},
    "source_type": {"type": "string", "description": "Provenance kind: drawer, conversation, file, URL, human, etc."},
    "source_id": {"type": "string", "description": "Stable identifier inside the source system"},
    "agent_id": {"type": "string", "description": "Agent proposing the memory"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "sensitivity": {"type": "string", "description": "Policy label; default normal"},
    "namespace": {"type": "string", "description": "Relative canonical knowledge namespace; default memory"},
    "title": {"type": "string", "description": "Human-readable filename hint"},
    "source_uri": {"type": "string", "description": "Optional source URI/path"},
    "source_version": {"type": "string", "description": "Optional immutable source revision"},
    "supersedes": {"type": "array", "items": {"type": "string"}},
}
_CANDIDATE_REQUIRED = ["content", "source_type", "source_id", "agent_id"]

TOOLS.update(
    {
        "mempalace_apprentice_status": {
            "description": "Show the opt-in Apprentice canonical-memory boundary configuration. No writes.",
            "input_schema": {"type": "object", "properties": {}},
            "handler": tool_apprentice_status,
        },
        "mempalace_apprentice_curate": {
            "description": (
                "Evaluate verbatim working memory for promotion into Apprentice's audited Git knowledge store. "
                "Side-effect free: returns promote/hold/reject plus the exact SHA-256 to approve."
            ),
            "input_schema": {
                "type": "object",
                "properties": dict(_CANDIDATE_PROPERTIES),
                "required": list(_CANDIDATE_REQUIRED),
            },
            "handler": tool_apprentice_curate,
        },
        "mempalace_apprentice_promote": {
            "description": (
                "Explicitly promote previously reviewed verbatim content into Apprentice's Git working tree. "
                "Re-curates before write and requires expected_sha256; never commits Git automatically."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    **_CANDIDATE_PROPERTIES,
                    "expected_sha256": {
                        "type": "string",
                        "description": "SHA-256 returned by curate; binds approval to exact content",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                },
                "required": [*_CANDIDATE_REQUIRED, "expected_sha256"],
            },
            "handler": tool_apprentice_promote,
        },
    }
)
