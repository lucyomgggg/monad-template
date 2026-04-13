"""
Monad: an LLM chooses when to call telos_search, telos_write, and http_get.
All runtime settings live in config.yaml; only API keys use environment variables.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv
from litellm import completion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _CONFIG_DIR / "config.yaml"
load_dotenv(_CONFIG_DIR / ".env", override=False)

_REQUIRED_KEYS = (
    "telos_base_url",
    "telos_timeout_sec",
    "telos_retry_max",
    "telos_retry_sleep_sec",
    "monad_id",
    "llm_model",
    "task",
    "interval_sec",
    "max_tool_rounds",
    "system_prompt",
    "tool_descriptions",
    "default_search_limit",
    "max_search_limit",
    "http_get_timeout_sec",
    "http_get_max_response_chars",
)

_TOOL_DESC_KEYS = ("telos_search", "telos_write", "telos_pass", "telos_reflect", "http_get")


class TelosClient:
    def __init__(
        self,
        base_url: str,
        monad_id: str,
        *,
        timeout: float,
        retry_max: int,
        retry_sleep: float,
    ) -> None:
        self._monad_id = monad_id
        self._retry_max = retry_max
        self._retry_sleep = retry_sleep
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def _request_json(self, method: str, path: str, json_body: dict[str, Any]) -> httpx.Response | None:
        attempt = 0
        while True:
            try:
                resp = self._client.request(method, path, json=json_body)
            except httpx.RequestError as exc:
                log.error("telos %s %s: %s", method, path, exc)
                return None
            if resp.status_code == 429 and attempt < self._retry_max:
                attempt += 1
                log.warning(
                    "telos 429; sleeping %ss (attempt %s/%s)",
                    self._retry_sleep,
                    attempt,
                    self._retry_max,
                )
                time.sleep(self._retry_sleep)
                continue
            return resp

    def search(self, query: str, limit: int) -> list[dict]:
        resp = self._request_json(
            "POST",
            "/api/v1/search",
            {"monad_id": self._monad_id, "query": query, "limit": limit},
        )
        if resp is None or not (200 <= resp.status_code < 300):
            return []
        data = resp.json()
        return data.get("results") or []

    def write(self, content: str, parent_ids: list[str] | None = None) -> str | None:
        resp = self._request_json(
            "POST",
            "/api/v1/write",
            {
                "monad_id": self._monad_id,
                "content": content,
                "parent_ids": parent_ids or [],
            },
        )
        if resp is None or resp.status_code == 413:
            return None
        if not (200 <= resp.status_code < 300):
            return None
        data = resp.json()
        nid = str(data.get("id", ""))
        return nid or None

    def reflect(self, limit: int = 5) -> list[dict]:
        """Retrieve this monad's own recent contributions via semantic search."""
        return self.search(f"recent contributions by {self._monad_id}", limit)


def load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        log.error("config.yaml not found: %s", _CONFIG_PATH)
        sys.exit(1)
    try:
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        log.error("config.yaml parse error: %s", e)
        sys.exit(1)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        log.error("config.yaml must be a mapping at the top level")
        sys.exit(1)
    return raw


def validate_config(cfg: dict[str, Any]) -> None:
    missing = [k for k in _REQUIRED_KEYS if k not in cfg]
    if missing:
        log.error("config.yaml missing required keys: %s", missing)
        sys.exit(1)

    td = cfg["tool_descriptions"]
    if not isinstance(td, dict):
        log.error("tool_descriptions must be a mapping")
        sys.exit(1)
    for k in _TOOL_DESC_KEYS:
        if k not in td or not str(td[k]).strip():
            log.error("tool_descriptions.%s is empty", k)
            sys.exit(1)

    if "fetch_allowed_hosts" not in cfg or not isinstance(cfg["fetch_allowed_hosts"], list):
        log.error("fetch_allowed_hosts must be a list (empty means allow all hosts)")
        sys.exit(1)

    task = str(cfg["task"]).strip()
    if not task:
        log.error("task must be non-empty")
        sys.exit(1)

    try:
        int(cfg["interval_sec"])
        int(cfg["max_tool_rounds"])
        int(cfg["default_search_limit"])
        int(cfg["max_search_limit"])
        float(cfg["telos_timeout_sec"])
        int(cfg["telos_retry_max"])
        float(cfg["telos_retry_sleep_sec"])
        float(cfg["http_get_timeout_sec"])
        int(cfg["http_get_max_response_chars"])
    except (TypeError, ValueError) as e:
        log.error("invalid numeric field: %s", e)
        sys.exit(1)

    if not str(cfg["telos_base_url"]).strip():
        log.error("telos_base_url is empty")
        sys.exit(1)

    tc = cfg.get("tool_choice", "auto")
    if isinstance(tc, str) and not str(tc).strip():
        log.error("tool_choice must not be empty when set as string")
        sys.exit(1)
    if not isinstance(tc, (str, dict)):
        log.error("tool_choice must be a string (e.g. auto, required) or an OpenAI-style object")
        sys.exit(1)

    if "parallel_tool_calls" in cfg and not isinstance(cfg["parallel_tool_calls"], bool):
        log.error("parallel_tool_calls must be a boolean when set")
        sys.exit(1)


def _search_quality_hint(hits: list[dict]) -> str:
    """Return a short hint about result quality to help the LLM decide whether to write."""
    if not hits:
        return "No results found. This topic may be unexplored in Telos."
    scores = [h.get("score", 0) for h in hits]
    top = max(scores) if scores else 0
    if top > 0.85:
        return "High similarity results found. Check carefully for duplicates before writing."
    if top > 0.7:
        return "Moderately related results. There may be room to extend or challenge existing knowledge."
    return "Weakly related results. This area may benefit from fresh exploration if you have genuine insight."


def build_tools(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    td = cfg["tool_descriptions"]
    return [
        {
            "type": "function",
            "function": {
                "name": "telos_search",
                "description": str(td["telos_search"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "telos_write",
                "description": str(td["telos_write"]),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "parent_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "telos_pass",
                "description": str(td["telos_pass"]),
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
                "description": str(td["telos_reflect"]),
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
                "description": str(td["http_get"]),
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
    ]


def _http_get_allowed(url: str, allowed: list[str] | None) -> bool:
    if not allowed:
        return True
    try:
        host = httpx.URL(url).host
    except Exception:
        return False
    return host in allowed


def run_tools(
    telos: TelosClient,
    cfg: dict[str, Any],
    name: str,
    arguments: str,
) -> str:
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON arguments: {e}"}, ensure_ascii=False)

    allowed_hosts = cfg["fetch_allowed_hosts"]
    allow = [str(h) for h in allowed_hosts] if allowed_hosts else None

    if name == "telos_search":
        q = args.get("query", "")
        default_lim = int(cfg["default_search_limit"])
        max_lim = int(cfg["max_search_limit"])
        lim = int(args.get("limit", default_lim))
        lim = max(1, min(lim, max_lim))
        hits = telos.search(str(q), lim)
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
        pids = args.get("parent_ids")
        if not isinstance(pids, list):
            pids = []
        pids = [str(x) for x in pids]
        nid = telos.write(content, pids)
        return json.dumps({"id": nid, "ok": nid is not None}, ensure_ascii=False)

    if name == "telos_pass":
        reason = str(args.get("reason", ""))
        log.info("telos_pass: %s", reason[:300])
        return json.dumps({"ok": True, "action": "pass", "reason": reason[:300]}, ensure_ascii=False)

    if name == "telos_reflect":
        default_lim = int(cfg["default_search_limit"])
        lim = int(args.get("limit", 5))
        lim = max(1, min(lim, default_lim))
        hits = telos.reflect(lim)
        return json.dumps({"recent_writes": hits, "count": len(hits)}, ensure_ascii=False)

    if name == "http_get":
        url = str(args.get("url", ""))
        if not _http_get_allowed(url, allow):
            return json.dumps({"error": "host not in fetch_allowed_hosts"}, ensure_ascii=False)
        timeout = float(cfg["http_get_timeout_sec"])
        max_chars = int(cfg["http_get_max_response_chars"])
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                r = client.get(url)
            text = r.text
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...(truncated)"
            return json.dumps(
                {"status_code": r.status_code, "body_prefix": text},
                ensure_ascii=False,
            )
        except httpx.RequestError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    return json.dumps({"error": f"unknown tool {name}"}, ensure_ascii=False)


def _assistant_message_to_dict(msg: Any) -> dict[str, Any]:
    if hasattr(msg, "model_dump"):
        return msg.model_dump()
    d: dict[str, Any] = {"role": "assistant", "content": getattr(msg, "content", None)}
    tc = getattr(msg, "tool_calls", None)
    if tc:
        out = []
        for c in tc:
            if hasattr(c, "model_dump"):
                out.append(c.model_dump())
            else:
                fn = getattr(c, "function", c)
                out.append(
                    {
                        "id": getattr(c, "id", ""),
                        "type": "function",
                        "function": {
                            "name": getattr(fn, "name", ""),
                            "arguments": getattr(fn, "arguments", "{}"),
                        },
                    }
                )
        d["tool_calls"] = out
    return d


def _tool_choice_for_round(cfg: dict[str, Any], round_i: int) -> str | dict[str, Any]:
    """
    First LLM call may use config tool_choice (e.g. 'required' to force an initial tool).
    Later rounds always use 'auto' so the model can answer in plain text after seeing tool results.
    """
    raw = cfg.get("tool_choice", "auto")
    if round_i > 0:
        return "auto"
    if isinstance(raw, dict):
        return raw
    s = str(raw).strip()
    return s if s else "auto"


def agent_turn(
    telos: TelosClient,
    cfg: dict[str, Any],
    messages: list[dict[str, Any]],
    model: str,
) -> None:
    tools = build_tools(cfg)
    max_rounds = int(cfg["max_tool_rounds"])
    parallel = cfg.get("parallel_tool_calls", True)
    if not isinstance(parallel, bool):
        parallel = True

    for round_i in range(max_rounds):
        tool_choice = _tool_choice_for_round(cfg, round_i)
        res = completion(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel,
        )
        choice = res.choices[0]
        msg = choice.message
        d = _assistant_message_to_dict(msg)
        messages.append(d)

        tool_calls = getattr(msg, "tool_calls", None) or d.get("tool_calls")
        if not tool_calls:
            log.info("assistant: %s", (d.get("content") or "")[:500])
            return

        for tc in tool_calls:
            if isinstance(tc, dict):
                tid = tc.get("id", "")
                fn = tc.get("function", {})
                name = fn.get("name", "")
                arguments = fn.get("arguments", "{}")
            else:
                tid = getattr(tc, "id", "")
                fn = getattr(tc, "function", None)
                name = getattr(fn, "name", "") if fn else ""
                arguments = getattr(fn, "arguments", "{}") if fn else "{}"

            payload = run_tools(telos, cfg, name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tid,
                    "content": payload,
                }
            )
        log.debug("tool round %s done", round_i + 1)

    log.warning("reached max_tool_rounds (%s)", max_rounds)


def run_once(cfg: dict[str, Any]) -> int:
    validate_config(cfg)

    base = str(cfg["telos_base_url"]).rstrip("/")
    monad_id = str(cfg["monad_id"])
    model = str(cfg["llm_model"])
    task = str(cfg["task"]).strip()
    interval = int(cfg["interval_sec"])
    system = str(cfg["system_prompt"])

    telos = TelosClient(
        base_url=base,
        monad_id=monad_id,
        timeout=float(cfg["telos_timeout_sec"]),
        retry_max=int(cfg["telos_retry_max"]),
        retry_sleep=float(cfg["telos_retry_sleep_sec"]),
    )
    try:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        agent_turn(telos, cfg, messages, model)
    finally:
        telos.close()

    return interval


def main() -> None:
    log.info("monad starting")
    while True:
        cfg = load_config()
        try:
            interval = run_once(cfg)
        except Exception:
            log.exception("run_once error")
            interval = int(cfg["interval_sec"])
        time.sleep(interval)


if __name__ == "__main__":
    main()
