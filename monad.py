"""
Monad Template
==============
差し替えるのは CONFIG セクションだけ。
ループ構造・Telos通信・エラーハンドリングは触らない。
"""

import os
import sys
import time
import logging
from pathlib import Path

import yaml
from litellm import completion
from telos_client import TelosClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# =============================================================================
# CONFIG LOADER — 触らない
# =============================================================================

_ALLOWED_FIELDS = {"monad_id", "interval_sec", "llm_model", "seed_query"}
_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] config.yaml の構文エラー: {e}", file=sys.stderr)
        sys.exit(1)
    if data is None:
        return {}
    unknown = set(data.keys()) - _ALLOWED_FIELDS
    if unknown:
        print(f"[ERROR] config.yaml に不正なフィールド: {unknown}", file=sys.stderr)
        sys.exit(1)
    return data


cfg = load_config()
MONAD_ID     = cfg.get("monad_id",     os.environ.get("MONAD_ID",     "monad-template"))
INTERVAL_SEC = cfg.get("interval_sec", int(os.environ.get("INTERVAL_SEC", 180)))
LLM_MODEL    = cfg.get("llm_model",    os.environ.get("LLM_MODEL",    "openai/gpt-4o-mini"))

# =============================================================================
# CONFIG — ここだけ変える
# =============================================================================

PERSONA = """
あなたは〇〇の専門家です。
与えられた情報から、仮説・問い・洞察を1〜3文で書いてください。
"""

def fetch_source() -> dict | None:
    """
    外部ソースからデータを取得する。
    sources/pubmed.py を参考に実装してください。
    戻り値: {"summary": str, "raw": str} or None
    """
    raise NotImplementedError("fetch_source() を実装してください")

# =============================================================================
# TELOS CLIENT / LLM — 触らない
# =============================================================================

telos = TelosClient.from_env(MONAD_ID)


def think(user_prompt: str) -> str:
    res = completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": PERSONA},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return res.choices[0].message.content.strip()

# =============================================================================
# LOOP — 触らない
# =============================================================================

def run():
    log.info(f"Starting {MONAD_ID}")
    while True:
        try:
            # --- Fetch型: 外部ソース → Telos ---
            source = fetch_source()
            if source is None:
                time.sleep(INTERVAL_SEC)
                continue

            context = telos.search(source["summary"])
            parent_ids = [r["id"] for r in context if r.get("score", 0) > 0.75]

            prompt = f"## 新しい情報\n{source['raw']}\n\n## 関連知識\n" + "\n".join(
                r["content"] for r in context
            )
            output = think(prompt)
            telos.write(output, parent_ids)
            log.info(f"written: {output[:60]}...")

            # --- Process型に切り替える場合は上記を以下に差し替える ---
            # SEED_QUERY = os.environ["SEED_QUERY"]
            # context = telos.search(SEED_QUERY)
            # if not context:
            #     time.sleep(INTERVAL_SEC)
            #     continue
            # prompt = "\n".join(r["content"] for r in context)
            # output = think(prompt)
            # telos.write(output, [r["id"] for r in context if r.get("score", 0) > 0.75])

        except Exception as e:
            log.error(f"loop error: {e}", exc_info=True)

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    run()
