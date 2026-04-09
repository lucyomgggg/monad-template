# monad-template

A minimal **Monad** (autonomous agent) that connects an LLM to **Telos** and optional HTTP resources. All behavior is driven by **`config.yaml`**; the entrypoint is **`monad.py`**.

---

## What is Telos?

**Telos** is a shared memory service for agents: text entries are embedded and stored; you can **search** by semantic similarity and **write** new memories. A typical deployment exposes HTTP APIs such as:

- `POST /api/v1/search` — vector search over stored memories  
- `POST /api/v1/write` — insert a new memory (with optional links to parent nodes)

This template talks to Telos over **`telos_base_url`** in `config.yaml`. It does **not** read Telos URLs from environment variables so that one file fully describes connectivity.

---

## What is a Monad?

In this ecosystem, a **Monad** is a long-running (or repeatedly invoked) process that:

1. Loads **`task`** and **`system_prompt`** from config.  
2. Lets the **LLM decide** when to call tools — **`telos_search`**, **`telos_write`**, and **`http_get`**.  
3. Sleeps **`interval_sec`**, then repeats (reloading `config.yaml` each iteration so you can edit behavior without rebuilding).

The model chooses the tool sequence; the template does not hardcode “search then write”. That makes it easy to specialize the agent by changing prompts and config only.

---

## How to run

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Point **`telos_base_url`** at your Telos Core instance and set **`monad_id`**, **`llm_model`**, **`task`**, and the rest of the required keys (see `monad.py`: `_REQUIRED_KEYS` and `validate_config()`).

3. Set provider credentials in the environment (for example **`OPENAI_API_KEY`** for OpenAI models).

4. Start:

   ```bash
   python monad.py
   ```

For containers, the included `Dockerfile` runs `python monad.py` after copying the project.

---

## Configuration overview

| Area | Purpose |
|------|---------|
| `telos_*` | HTTP client to Telos (URL, timeouts, 429 retries) |
| `monad_id` | Namespace for memories in Telos |
| `llm_model` | LiteLLM model id (e.g. `openai/gpt-4o-mini`) |
| `task` | User message each loop — what the agent should do |
| `system_prompt` | System instructions for the LLM |
| `tool_descriptions` | Strings exposed as tool descriptions to the model |
| `interval_sec` / `max_tool_rounds` | Loop timing and tool round cap |
| `fetch_allowed_hosts` | Optional allowlist for `http_get`; empty list allows any host |

Secrets stay in **environment variables**; everything else belongs in **`config.yaml`**.

---

## Customization examples

**Different goal each deployment**  
Change **`task`** and **`system_prompt`** only — e.g. “Summarize the latest search hits into one bullet” vs. “Propose a hypothesis and store it with parent links to supporting memories.”

**Separate memory namespaces**  
Use distinct **`monad_id`** values so Telos tags memories per agent.

**Tighter HTTP**  
Set **`fetch_allowed_hosts`** to e.g. `["api.slack.com", "www.ncbi.nlm.nih.gov"]` so **`http_get`** cannot reach arbitrary hosts.

**Cheaper or smarter models**  
Switch **`llm_model`** to another LiteLLM-supported id; keep the same tools.

**Fewer tool rounds**  
Lower **`max_tool_rounds`** if you want stricter caps on LLM turns per iteration.

**Faster loops**  
Reduce **`interval_sec`** for quicker cycles (mind rate limits on Telos and the LLM API).

---

## Extending the template

Advanced use cases can add new tools inside **`monad.py`** (extend `build_tools()` and `run_tools()`) — for example, calling another internal API or wrapping a database. Keep descriptions in **`config.yaml`** under a new key if you want them editable without code changes.

---

## Files

| File | Role |
|------|------|
| `monad.py` | LLM loop, Telos client, tool dispatch |
| `config.yaml` | All non-secret runtime settings |
| `requirements.txt` | Python dependencies |
| `.env.example` | Reminder for API keys (copy to `.env` if you use one) |
