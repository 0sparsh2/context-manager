# Context Manager

**Session context policies, warm segment store, and long-turn evals for AI agents** — inspired by [Arize Alex](https://youtu.be/esY99nYXxR4) (Sally-Ann DeLucia) and cross-validated against Anthropic, OpenAI, Google, Cursor, GitHub Copilot, Mem0, Zep, and recent research.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-26%20passed-green)](./tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

---

## Table of contents

- [What this is](#what-this-is)
- [Ideation & inspiration](#ideation--inspiration)
- [Approach](#approach)
- [Strengths](#strengths)
- [Limitations](#limitations)
- [Comparison to alternatives](#comparison-to-alternatives)
- [Metrics & benchmarks](#metrics--benchmarks)
- [Use cases & examples](#use-cases--examples)
- [Quick start](#quick-start)
- [Research & ongoing updates](#research--ongoing-updates)
- [Roadmap](#roadmap)

---

## What this is

A **framework-agnostic Python library** that sits between your agent orchestrator and the LLM API:

1. Keeps the **full transcript** (never silently deleted).
2. Builds a **hot context window** (what the model actually sees) via trim + tool policies.
3. **Archives** trimmed middle chunks to a **warm store** (SQLite) with IDs and previews.
4. Exposes **recall tools** so the model can pull archived content back when needed.
5. Ships a **long-session eval harness** (turn N → assert on turn N+1).

Optional: minimal agent loop with **mock**, **OpenAI**, or **NVIDIA NIM** (OpenAI-compatible API).

---

## Ideation & inspiration

### The problem

Long-running agents (coding, observability, support) accumulate **huge transcripts**: tool outputs, file reads, span dumps. Sending everything to the model causes:

- **Cost & latency** — token bloat on every turn.
- **Lost-in-the-middle** — early facts disappear or get buried.
- **False confidence** — the model answers from a truncated window without knowing what was dropped.

[Sally-Ann DeLucia’s talk on Alex](https://youtu.be/esY99nYXxR4) frames this as a **context management** problem, not a prompt problem: *agents fail from context, not prompts alone.*

### What Alex tried (and what we replicate)

| Experiment | Outcome |
|------------|---------|
| Keep only first ~100 chars | Broke follow-ups and reasoning |
| Full LLM summarization | Too inconsistent; no salience control |
| **Head + tail + middle in DB + recall tool** | Shipped; stable in production |
| Sub-agents for heavy span search | Main chat stays light |
| **Long-session evals** (e.g. 10 turns → test turn 11) | Catches late-session failures |

This repo **implements that session layer** as a small library you can embed in Cursor skills, MCP servers, or custom agents.

### Broader inspiration

- **Karpathy** — “context engineering” over prompt hacking; compiled notes vs live session.
- **Graphify** — repo-level compiled knowledge (complements session trim, does not replace it).
- **RhinoInsight / Context Engineering survey (2507.13334)** — layered stack: prune, compress, retrieve, delegate.
- **Weizhena Deep-Research-skills** — phased research workflow used to produce artifacts in `ai_agent_*_research/`.

Full research inventory: [`BUILD_READINESS.md`](./BUILD_READINESS.md), [`ai_agent_memory_research/report.md`](./ai_agent_memory_research/report.md).

---

## Approach

### Mental model

```text
COMPILED (slow)              SESSION (fast) — this repo
─────────────────            ─────────────────────────────
Karpathy wiki / Graphify ──┐
Mem0 / Zep (planned v2)  ──┼──► retrieve ──► HOT PROMPT ◄── trim + tool policy
                           │                      │
Obsidian / rules (static)──┘                      ▼
                                            WARM STORE (SQLite)
                                            recall_by_id / keyword
                                                      │
                                                      ▼
                                              SUB-AGENT (heavy work)
                                                      │
                                                      ▼
                                              EVAL: turn N+1 assertions
```

### Policies implemented (MVP)

| Layer | Mechanism |
|-------|-----------|
| **Trim** | `last_n` (OpenAI-style) or `head_tail` (Alex-style head + tail, archive middle) |
| **Tool results** | Keep latest result per tool name; older large outputs archived |
| **Warm store** | SQLite segments with ID, preview, full content |
| **Recall** | `recall_segment`, `recall_by_keyword`, `list_archived` (agent tools) |
| **Eval** | JSON fixtures: replay N turns, assert hot/recall/char bounds on turn N+1 |

### What we deliberately avoid (v1)

- **Uncontrolled summarization** as the primary compression strategy (Alex rejected it; we archive + recall instead).
- **Cross-chat semantic memory** (Mem0/Zep-style) — deferred to v2.
- **Full multi-agent orchestration** — sub-agent pattern is documented and fixture-tested; not a runtime framework yet.

---

## Strengths

| Strength | Why it matters |
|----------|----------------|
| **Deterministic policies** | Predictable hot window; easy to debug vs black-box summarization |
| **Full history preserved** | Audit, compliance, replay; nothing is truly “forgotten” |
| **Explicit recall** | Model (or harness) can fetch archived blobs by ID or keyword |
| **Head anchor** | Turn-1 goals / trace IDs stay visible (DeLucia turn-11 pattern) |
| **Long-session evals** | Regression-test “what did user ask on turn 1?” before users hit it |
| **Framework-agnostic** | Plain Python; works with OpenAI, NIM, or your own client |
| **Research-backed** | Compared to Anthropic compaction, OpenAI trim, Copilot memory, etc. |
| **Low dependency footprint** | Core package has zero required deps; optional `[llm]` for OpenAI SDK |

---

## Limitations

| Gap | Status |
|-----|--------|
| **Cross-session / long-term memory** | Not implemented (Copilot Memory, Mem0, Zep territory) |
| **Semantic retrieval** | Keyword + ID recall only; no embeddings |
| **Server-side compaction** | No Anthropic-style managed summarization API |
| **Prompt caching economics** | Not integrated (Google/Anthropic cache layers) |
| **Production UI** | CLI + library only |
| **MCP server** | Planned v2 (hooks exist conceptually, not shipped) |
| **Graphify / wiki automation** | Documented in research; not wired |
| **Vendor benchmark claims** | Mem0/Zep percentages marked cautious in research — not validated here |
| **Model latency** | Live NIM tests are slow (~1–3 min/round on `deepseek-v4-flash`) |

---

## Comparison to alternatives

*High-level positioning — see [`Comparison_synthesis_Arize_vs_industry.json`](./ai_agent_memory_research/results/Comparison_synthesis_Arize_vs_industry.json) for sources.*

| Product / pattern | Session curation | External memory | Compaction | Eval story |
|-------------------|------------------|-----------------|------------|------------|
| **This repo (Alex-style)** | Head/tail + archive + recall | SQLite warm store | Archive, not summarize | Long-session JSON fixtures |
| **Anthropic API** | Context editing, clear tools | — | **Server compaction** (summarize + drop) | Platform-dependent |
| **OpenAI Agents SDK** | **Trim last N** (deterministic) | Session helpers | Optional compression | Cookbook patterns |
| **Google Gemini / ADK** | Large windows | — | **Context caching** | Platform-dependent |
| **Cursor** | Rules + MCP (static/dynamic split) | — | Product-internal | — |
| **GitHub Copilot Memory** | — | **Cited cross-chat facts** | — | Re-verify facts |
| **Mem0 / Zep** | Can complement | **Semantic / temporal KG** | Varies | Vendor benchmarks |
| **LangGraph** | Checkpoints | Store integrations | — | Graph-level |
| **Claude Code / Codex** | Product compaction | AGENTS.md / skills | Subagents | — |

### Convergence (industry + Alex + this repo)

- Context engineering beats prompt-only tuning.
- Tool-heavy agents need **policies**, not “send everything.”
- **Delegate** heavy retrieval (sub-agents).
- **Test** long threads (turn 11 matters).

### Where this repo fits

You are not choosing Alex **or** industry — you are choosing **layers**:

1. **Curation policy** ← this repo  
2. Platform compaction ← Anthropic (if acceptable quality)  
3. Economic caching ← Google / Anthropic cache APIs  
4. Durable facts ← Copilot Memory / Mem0 / Zep (v2)  
5. Compiled repo knowledge ← Graphify / wiki (optional)  
6. Process audit ← RhinoInsight-style checklists (research only today)

---

## Metrics & benchmarks

### Automated test suite (local, no API)

| Suite | Result | Notes |
|-------|--------|-------|
| `pytest` | **26 / 26 passed** | Policies, store, agent loop, adapter mocks |
| `context-manager eval-all fixtures` | **6 / 6 passed** | Includes `fixtures/realworld/*` |
| Programmatic stress (`test_realworld_simulations.py`) | Pass | 20× span dumps, 50× file reads, DeLucia turn-11 |

### Context compression (Phase A — programmatic, no LLM)

| Metric | Value |
|--------|-------|
| Hot / full char ratio | **12.3%** (5,925 / 48,095) |
| Archived segments | **24** |
| Recall `RUN_00` from warm store | Pass |
| Head anchor (`trace_id` turn 1) in hot | Pass |

### Live NVIDIA NIM — `deepseek-ai/deepseek-v4-flash` (2026-05-22)

**Phase B** — 5 guided turns (~42 min):

| Metric | Value |
|--------|-------|
| Hot / full (final) | **~43%** (7,136 / 16,637 chars) |
| Archived segments | **174** |
| Tool usage | `search_spans`, `recall_segment`, `recall_by_keyword`, `list_archived` |
| Recall invoked | Yes |
| Tokens (total) | ~19,900 prompt / 585 completion |

**Phase C** — observability `DEMO_SCRIPT` (~31 min):

| Metric | Value |
|--------|-------|
| Hot / full (final) | **36.1%** (9,276 / 25,705 chars) |
| Archived segments | **315** |
| Turn 3: original `trace_id` without tools | Pass |
| Turn 4: `RUN_A` via `recall_segment` | Pass |

Run yourself: `python scripts/nim_deep_test.py` (see [Deep NIM test](#deep-nim-integration-test)).

*Research benchmarks (LOCOMO, LongMemEval, SWE-ContextBench) are mapped in research docs but not automated in this repo yet.*

---

## Use cases & examples

### 1. Observability / trace-debugging agent (Alex pattern)

**Scenario:** Agent runs many `search_spans` calls; each returns multi-KB payloads. User asks on turn 11: *“What was the original trace_id?”*

```python
from context_manager import ContextSession, ContextConfig, Message, TrimMode

session = ContextSession.create(
    ContextConfig(trim_mode=TrimMode.HEAD_TAIL, head_messages=1, tail_messages=6)
)
session.append(Message("system", "Observability agent."))
session.append(Message("user", "trace_id=checkout-failure-2026-03-15"))
# ... many tool messages ...
hot = session.get_hot_context()  # trimmed window for the LLM
full = session.recall(segment_id)  # pull archived span blob
```

**Fixture:** `fixtures/realworld/arize_observability_turn11.json`

### 2. Coding agent with repeated file reads

**Scenario:** Cursor-like agent reads files; only latest read stays hot; older reads archived.

**Fixture:** `fixtures/realworld/cursor_coding_agent.json`

### 3. Support chat with `last_n` trim

**Scenario:** OpenAI cookbook style — keep last N messages for a lightweight support bot.

**Fixture:** `fixtures/realworld/openai_support_last_n.json`

### 4. Sub-agent delegation

**Scenario:** Parent agent never sees raw sub-agent tool I/O — only a short summary.

**Fixture:** `fixtures/realworld/subagent_delegation.json`

### 5. Live agent loop + NVIDIA NIM

```bash
# .env: NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_NIM_API_BASE
context-manager demo --llm nim
context-manager demo -i --llm nim   # interactive
```

### 6. Long-session regression in CI

```bash
context-manager eval fixtures/realworld/arize_observability_turn11.json
context-manager eval-all fixtures
```

---

## Quick start

### Install

```bash
git clone https://github.com/0sparsh2/context-manager.git
cd context-manager
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
cp .env.example .env   # add NVIDIA_API_KEY or OPENAI_API_KEY
```

### Run tests

```bash
pytest -q
context-manager eval-all fixtures
./scripts/run_realworld_suite.sh
```

### CLI

| Command | Description |
|---------|-------------|
| `context-manager demo` | Scripted session (mock LLM) |
| `context-manager demo --llm nim` | Live NVIDIA NIM |
| `context-manager demo -i` | Interactive REPL |
| `context-manager eval <fixture.json>` | Single long-session eval |
| `context-manager inspect <fixture.json>` | Hot vs full stats |

### Deep NIM integration test

```bash
python scripts/nim_deep_test.py           # phases A + B + C (~45–90 min)
python scripts/nim_deep_test.py --phase a # seconds, no API
```

### Library

```python
from context_manager import MinimalAgentLoop, LLMConfig, run_scripted_demo

results = run_scripted_demo(verbose=False, llm_config=LLMConfig.from_env(provider="nim"))
print(results[-1].hot_chars, results[-1].full_chars)
```

---

## Research & ongoing updates

This repository includes **validated research artifacts** (not just code):

| Path | Contents |
|------|----------|
| `ai_agent_context_management_research/` | 10 topics — Anthropic, Cursor, MCP, benchmarks |
| `ai_agent_memory_research/` | 19 JSON items + reports — DeLucia transcript, Mem0, Zep, synthesis |
| `.cursor/skills/deep-research/` | Repeatable phased research skill for this repo |
| `BUILD_READINESS.md` | Build verdict, architecture freeze, MVP scope |

**Ongoing process:** Topics marked *uncertain* or *v2* in research (vendor benchmark %, Claude Code internals, full Mem0 integration) will be updated on a **regular cadence** via deep-research passes; git history will reflect incremental research + code changes.

To validate research JSON after edits:

```bash
python .cursor/skills/deep-research/scripts/validate_json.py ai_agent_memory_research/results/
```

---

## Roadmap

| Version | Scope |
|---------|--------|
| **v1 (current)** | Python package, policies, SQLite store, eval CLI, mock + OpenAI + NIM adapter |
| **v2** | MCP server (recall + policy hooks) |
| **v3** | Cursor skill wrapping eval + inspect |
| **Future** | Mem0/Zep hooks, optional compaction plugin, Graphify integration spike |

---

## Project structure

```text
src/context_manager/
  policies/       # trim, tool-result policies
  store/          # SQLite segment store
  session.py      # ContextSession orchestration
  eval/           # long-session harness
  agent/          # loop, mock/OpenAI/NIM adapters
fixtures/         # eval JSON (incl. realworld/)
ai_agent_*_research/  # deep-research artifacts
scripts/          # nim_deep_test, run_realworld_suite
```

---

## License

MIT — see [LICENSE](./LICENSE).

---

## Acknowledgments

- [Arize — How we solved Context Management in Agents](https://youtu.be/esY99nYXxR4) (Sally-Ann DeLucia)
- [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills) research workflow
- [NVIDIA NIM](https://docs.api.nvidia.com/nim/reference/llm-apis) for OpenAI-compatible inference
