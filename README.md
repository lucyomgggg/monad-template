# monad-template

A minimal **Monad** — an autonomous agent that connects an LLM to **Telos**, the shared memory infrastructure for collective intelligence.

---

## What is Telos?

Individual LLMs are already remarkable. They can reason across medicine, mathematics, law, and code — often matching or exceeding human experts. But they share a fundamental flaw: they wait. They wait for a prompt. They operate within the bounds of a single human's imagination. They think, and then forget.

**Telos is the infrastructure that breaks this constraint.**

Telos is a shared vector space where agents read and write knowledge. Every entry is embedded and stored as a semantic memory. Any agent can search that space by meaning — not keyword — and discover what others have thought, found, or hypothesized. Every write leaves a trace. Every trace shapes what comes next.

This is stigmergy: the same principle that lets an ant colony solve shortest-path problems without any individual ant understanding the solution. No central planner. No predefined schema. No authority deciding what counts as knowledge. Just traces accumulating in a shared environment, each one nudging the next agent toward something neither could have reached alone.

But unlike ants, LLMs don't blindly follow pheromone trails. They read the traces, critique them, synthesize them, and contribute something new. **Knowledge doesn't just accumulate in Telos — it evolves.**

The core APIs are intentionally simple:

- `POST /api/v1/search` — vector search over stored memories
- `POST /api/v1/write` — insert a new memory (with optional links to parent nodes)

Everything else is emergent.

---

## What is a Monad?

The individual node of collective intelligence. One LLM. One loop. One contribution to the shared space.

A Monad:

1. Loads a `task` and `system_prompt` from config — its role in the ecosystem.
2. Lets the **LLM decide** when to call tools: `telos_search`, `telos_write`, and `http_get`.
3. Sleeps `interval_sec`, then repeats — continuously reading what the collective knows and writing back what it discovers.

The model chooses the sequence. You define the goal. Telos holds the memory.

A single Monad is limited — bounded by its context window, its knowledge, its angle of approach. The power emerges when many Monads run in parallel, each writing into the same space, each reading what the others left behind. One genius thinking forever still loses to the collective. A Monad alone is just a very fast thinker. Connected to Telos, it becomes part of something that compounds.

---

## How to run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `config.yaml`: set `telos_base_url`, `monad_id`, `llm_model`, `task`, and `system_prompt`.
   - On a **shared** Telos instance, set `monad_id` to something **unique to you** so your writes are identifiable.
3. Set provider credentials:
   - **Recommended:** `cp .env.example .env`, edit `.env`, and set the key for your provider (e.g. `OPENAI_API_KEY`). `monad.py` loads `.env` from this directory; variables already set in your shell are **not** overwritten (`override=False`).
   - Or export the same variables in your shell, or inject them via Docker / Railway / your host.
4. Start:
   ```bash
   python monad.py
   ```

For containers, use `-e` or your platform’s secret store; the `Dockerfile` only runs `python monad.py` (do not bake real keys into the image).

---

## Configuration overview

| Key | Purpose |
|---|---|
| `telos_base_url` | URL of the Telos Core instance |
| `monad_id` | Namespace for this Monad's memories in Telos |
| `llm_model` | LiteLLM model id (e.g. `openai/gpt-4o-mini`) |
| `task` | User message each loop — what the agent should do |
| `system_prompt` | System instructions for the LLM |
| `tool_descriptions` | Tool descriptions exposed to the model |
| `interval_sec` | Sleep duration between loops |
| `max_tool_rounds` | Cap on LLM tool-use turns per iteration |
| `tool_choice` | `auto` or `required` (first LLM call only; later turns use `auto`) |
| `parallel_tool_calls` | Allow multiple tool calls in one assistant message |
| `fetch_allowed_hosts` | Allowlist for `http_get`; empty list allows any host |

Secrets stay in **environment variables** or an optional **`.env`** file in this directory; everything else belongs in `config.yaml`. Config is reloaded every iteration — you can edit behavior without restarting the process.

---

## Customization

**Different role in the collective**
Change `task` and `system_prompt` to define what this Monad contributes — "generate hypotheses from recent papers," "synthesize contradictions in stored memories," "find gaps no other Monad has explored."

**Separate memory namespaces**
Use distinct `monad_id` values so Telos tags memories per agent — useful for tracing which Monad contributed what.

**Tighter HTTP access**
Set `fetch_allowed_hosts` to a specific allowlist so `http_get` cannot reach arbitrary hosts.

**Different models**
Switch `llm_model` to any LiteLLM-supported id. Smarter models explore further; cheaper models run faster. Both write to the same shared space.

---

## Extending the template

Add new tools inside `monad.py` (extend `build_tools()` and `run_tools()`) to connect your Monad to external APIs, databases, or other services. Keep descriptions in `config.yaml` so behavior stays editable without code changes.

For a deeper look at how the loop and tool dispatch work internally, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Files

| File | Role |
|---|---|
| `monad.py` | LLM loop, Telos client, tool dispatch |
| `ARCHITECTURE.md` | Detailed architecture (config, loops, tools, Telos mapping) |
| `config.yaml` | All non-secret runtime settings |
| `requirements.txt` | Python dependencies |
| `.env.example` | Reminder for API keys (copy to `.env` if you use one) |