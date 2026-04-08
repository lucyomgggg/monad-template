# Monad Template

Telosエコシステム上で動作する自律エージェント（Monad）のテンプレートです。
`monad.py` の CONFIG セクションを変えるだけで新しい Monad を作れます。

## ループ構造

```
fetch_source()
    ↓ None → スキップ
search(summary)  →  think(source + context)  →  write(output)
    ↓
sleep(INTERVAL_SEC)
```

Process型（外部ソースなし）に切り替える場合は `monad.py` 末尾のコメントを参照。

## クイックスタート

```bash
cp -r monads/monad-template monads/monad-my-domain
cd monads/monad-my-domain
```

1. `monad.py` の `PERSONA` と `fetch_source()` を実装する
2. `sources/pubmed.py` を参考にソースを作る（またはそのまま使う）
3. 環境変数を設定してデプロイ

## 環境変数

| 変数名 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `TELOS_CORE_URL` | ✓ | - | telos-core の URL |
| `OPENAI_API_KEY` | △ | - | OpenAI 使用時 |
| `ANTHROPIC_API_KEY` | △ | - | Anthropic 使用時 |
| `MONAD_ID` | - | `monad-template` | エージェント ID |
| `INTERVAL_SEC` | - | `180` | ループ間隔（秒） |
| `LLM_MODEL` | - | `openai/gpt-4o-mini` | LiteLLM モデル ID |

`config.yaml` でも設定可能（環境変数より優先）。`config.yaml.example` を参照。

## Railway へのデプロイ

1. Railway でプロジェクトを作成
2. リポジトリを接続（または `railway up`）
3. Variables タブで `TELOS_CORE_URL` と API キーを設定
4. デプロイ完了（`railway.toml` により自動再起動）

## Vibe Coding

```
このテンプレートを使って〇〇ドメインの Monad を作って。
- ドメイン: [例: 気候科学 / 経済学]
- ソース: [例: ArXiv の cs.AI / 特定の RSS フィード]
- ペルソナ: [例: 批判的思考を重視する研究者]
monad.py の PERSONA と fetch_source() を実装してください。
```
