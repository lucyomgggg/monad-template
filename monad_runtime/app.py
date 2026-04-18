from __future__ import annotations

import logging
import time
from typing import Any

from monad_runtime.config import load_config, validate_config
from monad_runtime.llm import agent_turn
from monad_runtime.telos import TelosClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


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
