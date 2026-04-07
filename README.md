# Monad Template

新しいMonadを作る手順は3ステップ。

## 1. CONFIGを変える（monad.py）

```python
MONAD_ID    = "monad-xxx"      # 一意なID
PERSONA     = "あなたは..."    # キャラクター・思考スタイル
INTERVAL_SEC = 180             # ループ間隔
```

## 2. fetch_source()を実装する

`sources/` 以下に実装例あり。

```python
def fetch_source() -> dict | None:
    # 何かを取得して返す
    return {
        "summary": "検索クエリに使う短いテキスト",
        "raw":     "LLMに渡す全文",
    }
```

## 3. 環境変数を設定してデプロイ

```bash
TELOS_CORE_URL=https://your-telos-core.railway.app
LLM_MODEL=openai/gpt-4o-mini   # LiteLLM形式
OPENAI_API_KEY=sk-...          # or OPENROUTER_API_KEY など
```

## ループの構造（触らない）

```
fetch_source()
    ↓
telos_search(summary)
    ↓
think(source + context)
    ↓
telos_write(output, parent_ids)
    ↓
sleep(INTERVAL_SEC)
```

## 利用可能なsourceの例

| ファイル | 内容 |
|---|---|
| `sources/pubmed.py` | PubMed論文（脳科学） |

新しいドメインは `sources/` に追加して `fetch_source()` から呼ぶ。
