# Build readiness — Context Manager

**Date:** 2026-05-14  
**Purpose:** Integrate research, evaluate completeness, decide if more discovery is needed before implementation.

---

## Verdict

| Question | Answer |
|----------|--------|
| **Is more general research required?** | **No** — sufficient for MVP architecture and stack choices. |
| **Is more product definition required?** | **Yes** — one short MVP spec (runtime + scope) before coding. |
| **Ready to build?** | **Yes**, after you confirm MVP scope below (≈15 min decision, not weeks of research). |

---

## Research inventory (integrated)

### Track A — Context management (`ai_agent_context_management_research/`)

10 items · validated JSON · [`report.md`](ai_agent_context_management_research/report.md)

| Topic | Key takeaway |
|-------|----------------|
| Anthropic API | Compaction + context editing + caching |
| Claude Code | Product compaction / truncation |
| Cursor | Rules + MCP |
| OpenAI Codex | AGENTS.md, skills, MCP |
| Copilot indexing | Semantic repo index |
| MCP | Tools/resources standard |
| Long-context benchmarks | NoLiMa, NeedleChain, Haystack-style |
| SWE-ContextBench | Curated context beats volume |
| Mem0 | External memory layer |
| Arize talk (early) | Framing only; superseded by transcript-backed track B |

### Track B — Memory + industry comparison (`ai_agent_memory_research/`)

19 items · validated JSON · [`report.md`](ai_agent_memory_research/report.md)

| Topic | Key takeaway |
|-------|----------------|
| DeLucia / Alex (transcript) | Head/tail + DB recall; reject naive summarization; sub-agents; 10→11 evals |
| Industry leaders | Anthropic, OpenAI, Google, Cursor, GitHub Copilot |
| Academic | Survey 2507.13334, RhinoInsight 2511.18743 |
| Vendors | Mem0, Zep, Letta |
| Framework | LangGraph checkpoints |
| Compiled knowledge | Karpathy wiki + Obsidian, Graphify |
| Synthesis | `Comparison_synthesis_Arize_vs_industry.json` |

### Tooling

- [`@deep-research` skill](.cursor/skills/deep-research/SKILL.md) — repeatable phased research in this repo  
- Reference clone: `deep-research-skills-ref/` (upstream only)

---

## Evaluation scorecard

| Criterion | Status | Notes |
|-----------|--------|-------|
| Primary source (DeLucia talk) | ✅ | Transcript-backed JSON |
| Big tech patterns (2025–2026) | ✅ | Anthropic, OpenAI, Google, MS/GitHub, Cursor |
| Academic framing | ✅ | Survey + RhinoInsight + SWE-ContextBench |
| Memory vendors | ✅ | Mem0, Zep, Letta (benchmark claims marked cautious) |
| Compiled knowledge (Karpathy, Graphify) | ✅ | Added in readiness pass |
| Cross-walk / synthesis | ✅ | Comparison JSON + reports |
| JSON schema validation | ✅ | 19/19 memory track (run validator after edits) |
| **Product MVP defined** | ✅ | See `README.md` + MVP table below |
| **Runtime chosen** | ✅ | Python package (`src/context_manager/`) |
| **Prototype / spike** | ✅ | `pytest` + `context-manager eval` passing |

**Residual uncertainty (acceptable for build):** vendor benchmark percentages, exact Claude Code internals, Zep latency claims — validate in implementation spikes, not more desk research.

---

## What we are *not* researching further (diminishing returns)

- More NIAH/long-context papers (already have benchmark map)  
- Additional memory startups unless MVP targets enterprise temporal KG  
- Deeper Claude Code leak / cache-invalidation details (platform-specific spike later)  
- Duplicate pass on same vendors in Track A vs B (merged in synthesis)

---

## Recommended architecture (frozen for build)

From integrated research — **hybrid stack**:

1. **Stable prefix** — rules / system prompt (+ optional prompt cache)  
2. **Session policy** — trim or head/tail; latest tool result; clear old tool output  
3. **Warm store** — ID + preview + recall tool (Alex pattern)  
4. **Heavy work** — sub-agent or pre-built index (Graphify optional for repo)  
5. **Cold memory** — v2: Mem0 or cited facts; v1 can defer  
6. **Compiled notes** — optional Obsidian/wiki for research artifacts  
7. **Evals** — long-session N→N+1 harness (required in MVP)

---

## MVP scope proposal (confirm before build)

**Goal:** A small, testable **context policy library** + **eval harness**, usable from Cursor via skill or Python import.

| In MVP | Out of MVP (v2) |
|--------|------------------|
| Message list → apply trim policy (last-N **or** head/tail) | Full Mem0/Zep integration |
| Tool-result policy (keep latest / clear older) | Graphify pipeline automation |
| Segment store (SQLite) + recall-by-id tool interface | Cross-chat semantic memory |
| Long-session eval CLI (load N, assert turn N+1) | UI / Obsidian plugin |
| Unit tests + 2–3 fixture conversations | Multi-agent orchestration framework |

**Suggested runtime:** Python 3.11+ package in `src/context_manager/` (framework-agnostic; Cursor skill wraps it).

---

## Pre-build checklist

- [x] Research tracks complete and cross-linked  
- [x] Industry + academic comparison documented  
- [x] Karpathy / Graphify positioned in stack  
- [x] **MVP table confirmed** (user)  
- [x] **Runtime: Python package** (MCP + Cursor skill → v2/v3)  
- [x] `pyproject.toml` + `src/context_manager/`  
- [x] Policy + store + eval implemented  
- [x] Dogfood: `fixtures/tool_spam_then_followup.json` PASS  

## Run the MVP

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
context-manager eval fixtures/tool_spam_then_followup.json
```

---

## Integration map (single mental model)

```text
COMPILED (slow)          SESSION (fast)
─────────────────        ─────────────────
Karpathy wiki     ──┐
Graphify graph    ──┼──► retrieve ──► HOT PROMPT ◄── trim / tool policy
Mem0/Zep (v2)     ──┘                      │
                                           ▼
                                    SUB-AGENT (heavy)
                                           │
                                           ▼
                                    EVAL: turn N+1
```

---

## Next step

**No further general research.** Proceed to build when you confirm:

1. MVP scope table (or edits)  
2. Python package vs other runtime  

Then implementation starts with: **store + trim policy + eval harness** (the highest-leverage Alex lessons with the fewest dependencies).
