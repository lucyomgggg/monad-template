"""
Monad Template
==============
差し替えるのは CONFIG セクションだけ。
ループ構造・Telos通信・エラーハンドリングは触らない。
"""

import os
import time
import logging
import requests
from litellm import completion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# =============================================================================
# CONFIG — ここだけ変える
# =============================================================================

MONAD_ID = "monad-template"          # 各Monadで一意なID

PERSONA = """
あなたは〇〇の専門家です。
与えられた情報から、仮説・問い・洞察を1〜3文で書いてください。
既存の知識との接続を意識してください。
"""

INTERVAL_SEC = 180                   # ループ間隔（秒）
SEARCH_LIMIT = 5                     # Telos検索の取得件数

def fetch_source() -> dict | None:
    """
    入力ソースを取得する。
    戻り値: { "summary": str, "raw": str } or None（取得失敗時）

    例: ArXiv, PubMed, RSS, DB, etc. をここに実装する。
    """
    raise NotImplementedError("fetch_source() を実装してください")

# =============================================================================
# TELOS CLIENT — 触らない
# =============================================================================

TELOS_URL = os.environ["TELOS_CORE_URL"].rstrip("/")

def telos_search(query: str) -> list[dict]:
    try:
        res = requests.post(
            f"{TELOS_URL}/api/v1/search",
            json={"monad_id": MONAD_ID, "query": query, "limit": SEARCH_LIMIT},
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("results", [])
    except Exception as e:
        log.warning(f"search failed: {e}")
        return []

def telos_write(content: str, parent_ids: list[str] = []) -> str | None:
    try:
        res = requests.post(
            f"{TELOS_URL}/api/v1/write",
            json={"monad_id": MONAD_ID, "content": content, "parent_ids": parent_ids},
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("id")
    except Exception as e:
        log.warning(f"write failed: {e}")
        return None

# =============================================================================
# LLM — 触らない
# =============================================================================

LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")

def think(user_prompt: str) -> str:
    res = completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": PERSONA},
            {"role": "user", "content": user_prompt},
        ],
    )
    return res.choices[0].message.content.strip()

# =============================================================================
# LOOP — 触らない
# =============================================================================

def build_prompt(source: dict, context: list[dict]) -> str:
    ctx_text = "\n\n".join(
        f"[既存知識 score={r['score']:.2f}]\n{r['content']}"
        for r in context
    ) if context else "（まだ関連知識なし）"

    return f"""
## 新しい情報
{source['raw']}

## Telos空間の関連知識
{ctx_text}

上記をもとに、仮説・問い・洞察を書いてください。
"""

def run():
    log.info(f"Starting {MONAD_ID}")
    while True:
        try:
            # 1. 入力取得
            source = fetch_source()
            if source is None:
                log.info("source not available, skipping")
                time.sleep(INTERVAL_SEC)
                continue

            # 2. Telos検索
            context = telos_search(source["summary"])
            parent_ids = [r["id"] for r in context if r.get("score", 0) > 0.75]
            log.info(f"search hits: {len(context)}, parents: {len(parent_ids)}")

            # 3. LLMで思考
            prompt = build_prompt(source, context)
            output = think(prompt)
            log.info(f"output: {output[:80]}...")

            # 4. Telosに書き込み
            node_id = telos_write(output, parent_ids)
            log.info(f"written: {node_id}")

        except Exception as e:
            log.error(f"loop error: {e}", exc_info=True)

        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    run()
