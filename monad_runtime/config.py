from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = CONFIG_DIR / "config.yaml"
load_dotenv(CONFIG_DIR / ".env", override=False)

CORE_SEARCH_LIMIT_MAX = 20

REQUIRED_KEYS = (
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

TOOL_DESC_KEYS = ("telos_search", "telos_write", "telos_pass", "telos_reflect", "http_get")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log.error("config.yaml not found: %s", CONFIG_PATH)
        sys.exit(1)
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        log.error("config.yaml parse error: %s", exc)
        sys.exit(1)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        log.error("config.yaml must be a mapping at the top level")
        sys.exit(1)
    return raw


def validate_config(cfg: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_KEYS if key not in cfg]
    if missing:
        log.error("config.yaml missing required keys: %s", missing)
        sys.exit(1)

    tool_descriptions = cfg["tool_descriptions"]
    if not isinstance(tool_descriptions, dict):
        log.error("tool_descriptions must be a mapping")
        sys.exit(1)
    for key in TOOL_DESC_KEYS:
        if key not in tool_descriptions or not str(tool_descriptions[key]).strip():
            log.error("tool_descriptions.%s is empty", key)
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
    except (TypeError, ValueError) as exc:
        log.error("invalid numeric field: %s", exc)
        sys.exit(1)

    if int(cfg["max_search_limit"]) > CORE_SEARCH_LIMIT_MAX:
        log.error("max_search_limit must be <= %s", CORE_SEARCH_LIMIT_MAX)
        sys.exit(1)

    if not str(cfg["telos_base_url"]).strip():
        log.error("telos_base_url is empty")
        sys.exit(1)

    tool_choice = cfg.get("tool_choice", "auto")
    if isinstance(tool_choice, str) and not str(tool_choice).strip():
        log.error("tool_choice must not be empty when set as string")
        sys.exit(1)
    if not isinstance(tool_choice, (str, dict)):
        log.error("tool_choice must be a string (e.g. auto, required) or an OpenAI-style object")
        sys.exit(1)

    if "parallel_tool_calls" in cfg and not isinstance(cfg["parallel_tool_calls"], bool):
        log.error("parallel_tool_calls must be a boolean when set")
        sys.exit(1)
