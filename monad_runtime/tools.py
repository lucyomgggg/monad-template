from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from monad_runtime.telos import TelosClient

log = logging.getLogger(__name__)


def _search_quality_hint(hits: list[dict]) -> str:
    """Return a short hint about result quality to help the LLM decide whether to write."""
    if not hits:
        return "No results found. This topic may be unexplored in Telos."
    scores = [hit.get("score", 0) for hit in hits]
    top_score = max(scores) if scores else 0
    if top_score > 0.85:
        return "High similarity results found. Check carefully for duplicates before writing."
    if top_score > 0.7:
        return "Moderately related results. There may be room to extend or challenge existing knowledge."
    return "Weakly related results. This area may benefit from fresh exploration if you have genuine insight."


def build_tools(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    tool_descriptions = cfg["tool_descriptions"]
    return [
        {
            "type": "function",
            "function": {
                "name": "telos_search",
                "description": str(tool_descriptions["telos_search"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                        "kind": {"type": "string"},
                        "scope_kind": {"type": "string"},
                        "scope_id": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "telos_write",
                "description": str(tool_descriptions["telos_write"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "parent_ids": {"type": "array", "items": {"type": "string"}},
                        "kind": {"type": "string"},
                        "scope_kind": {"type": "string"},
                        "scope_id": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "telos_pass",
                "description": str(tool_descriptions["telos_pass"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Why this loop does not warrant a write."},
                    },
                    "required": ["reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "telos_reflect",
                "description": str(tool_descriptions["telos_reflect"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of recent entries to retrieve (default 5)."},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "http_get",
                "description": str(tool_descriptions["http_get"]),
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
    ]


def _http_get_allowed(url: str, allowed_hosts: list[str] | None) -> bool:
    if not allowed_hosts:
        return True
    try:
        host = httpx.URL(url).host
    except Exception:
        return False
    return host in allowed_hosts


def run_tools(
    telos: TelosClient,
    cfg: dict[str, Any],
    name: str,
    arguments: str,
) -> str:
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"invalid JSON arguments: {exc}"}, ensure_ascii=False)

    allowed_hosts = cfg["fetch_allowed_hosts"]
    allow = [str(host) for host in allowed_hosts] if allowed_hosts else None

    if name == "telos_search":
        query = args.get("query", "")
        default_limit = int(cfg["default_search_limit"])
        max_limit = int(cfg["max_search_limit"])
        limit = int(args.get("limit", default_limit))
        limit = max(1, min(limit, max_limit))
        hits = telos.search(
            str(query),
            limit,
            kind=str(args["kind"]) if args.get("kind") is not None else None,
            scope_kind=str(args["scope_kind"]) if args.get("scope_kind") is not None else None,
            scope_id=str(args["scope_id"]) if args.get("scope_id") is not None else None,
        )
        result = {
            "results": hits,
            "meta": {
                "result_count": len(hits),
                "top_score": hits[0]["score"] if hits else None,
                "hint": _search_quality_hint(hits),
            },
        }
        return json.dumps(result, ensure_ascii=False)

    if name == "telos_write":
        content = str(args.get("content", ""))
        parent_ids = args.get("parent_ids")
        if not isinstance(parent_ids, list):
            parent_ids = []
        parent_ids = [str(value) for value in parent_ids]
        raw_metadata = args.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else None
        node_id = telos.write(
            content,
            parent_ids,
            kind=str(args["kind"]) if args.get("kind") is not None else None,
            scope_kind=str(args["scope_kind"]) if args.get("scope_kind") is not None else None,
            scope_id=str(args["scope_id"]) if args.get("scope_id") is not None else None,
            metadata=metadata,
        )
        return json.dumps({"id": node_id, "ok": node_id is not None}, ensure_ascii=False)

    if name == "telos_pass":
        reason = str(args.get("reason", ""))
        log.info("telos_pass: %s", reason[:300])
        return json.dumps({"ok": True, "action": "pass", "reason": reason[:300]}, ensure_ascii=False)

    if name == "telos_reflect":
        default_limit = int(cfg["default_search_limit"])
        limit = int(args.get("limit", 5))
        limit = max(1, min(limit, default_limit))
        hits = telos.reflect(limit)
        return json.dumps({"recent_writes": hits, "count": len(hits)}, ensure_ascii=False)

    if name == "http_get":
        url = str(args.get("url", ""))
        if not _http_get_allowed(url, allow):
            return json.dumps({"error": "host not in fetch_allowed_hosts"}, ensure_ascii=False)
        timeout = float(cfg["http_get_timeout_sec"])
        max_chars = int(cfg["http_get_max_response_chars"])
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url)
            text = response.text
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...(truncated)"
            return json.dumps(
                {"status_code": response.status_code, "body_prefix": text},
                ensure_ascii=False,
            )
        except httpx.RequestError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return json.dumps({"error": f"unknown tool {name}"}, ensure_ascii=False)
