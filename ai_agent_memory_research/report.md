# Deep research report: AI agent memory — video, market, papers, and industry comparison

**Methodology:** `@deep-research` skill / [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills) / [RhinoInsight](https://arxiv.org/html/2511.18743v1). Artifacts: `outline.yaml`, `fields.yaml`, **17** validated JSON files in `results/`, as-of **2026-05-14**.

**Answer to your question:** The **first** pass compared vendors and some papers at a high level. This pass **explicitly** compares **Arize Alex (DeLucia talk)** to **current research** and **big industry leaders**—see [Comparison matrix](#comparison-matrix-arize-alex-vs-research--industry) and `results/Comparison_synthesis_Arize_vs_industry.json`.

---

## Table of contents

### Primary source
1. [DeLucia / Arize Alex (transcript-backed)](#1-delucia--arize-alex)

### Industry leaders (context / memory)
2. [Anthropic API — compaction & context editing](#2-anthropic-api)
3. [Claude Code](#3-claude-code)
4. [OpenAI Agents SDK — trimming & sessions](#4-openai-agents-sdk)
5. [Google Gemini / ADK — caching & compression](#5-google-gemini--adk)
6. [Cursor IDE](#6-cursor-ide)
7. [GitHub Copilot / Microsoft memory](#7-github-copilot--microsoft)

### Academic / research
8. [Survey — Context Engineering (2507.13334)](#8-survey-context-engineering)
9. [RhinoInsight (2511.18743)](#9-rhinoinsight)
10. [Memory benchmarks (LOCOMO, LongMemEval, etc.)](#10-memory-benchmarks)

### Memory products & frameworks
11. [Mem0](#11-mem0) · [Zep](#12-zep) · [Letta](#13-letta) · [OpenAI sessions](#14-openai-sessions) · [LangGraph](#15-langgraph) · [Market landscape](#16-market-landscape)

### Synthesis
17. [**Comparison matrix: Arize Alex vs research & industry**](#comparison-matrix-arize-alex-vs-research--industry)

---

## Executive synthesis

### DeLucia / Alex (what the talk actually claims)

[How we solved Context Management in Agents](https://youtu.be/esY99nYXxR4) — **Sally-Ann DeLucia**, Head of Product at **Arize**, on **Alex** (observability-native agent harness). Core line: **agents fail from context, not prompts alone.** Production stack after failed experiments:

| Tried | Result |
|--------|--------|
| First ~100 chars only | Broke follow-ups / reasoning |
| Full LLM summarization | Too inconsistent; no salience control |
| **Head ~100 + tail ~100 + middle in DB + tool recall** | Shipped; stable for months at time of talk |
| **Sub-agents** for span search | Main chat stays light |
| **Long-session evals** (e.g. 10 turns → test 11th) | Makes late failures testable |

**Still building:** cross-chat **long-term memory**, principled context budget, more cache sophistication (Q&A: IDs + preview tool today).

Full detail: `results/DeLucia_talk_video.json`.

---

## Comparison matrix: Arize Alex vs research & industry

| Layer | **Arize Alex (DeLucia)** | **Industry leaders** | **Research** |
|--------|--------------------------|----------------------|--------------|
| **In-window curation** | Fixed head/tail heuristic; latest tool output | OpenAI: **trim last N** (deterministic); Anthropic: **clear tool results** | Survey 2507.13334: *context management / compression* |
| **Lossy compression** | Rejected **ad hoc** summarization | Anthropic: **server compaction** (summarize + drop) | RhinoInsight: **prune noise** before model sees it |
| **External recall** | Middle → **DB**, tool fetch by ID + preview | Mem0 / Zep: semantic or temporal retrieval | Mem0 arXiv 2504.19413; Zep arXiv 2501.13956 |
| **Cross-session memory** | **Not yet** (admitted gap) | GitHub **Copilot Memory** (cited facts, re-verify) | Letta core/recall/archival blocks |
| **Heavy tool/data work** | **Sub-agents** | Claude Code / Codex subagents; LangGraph branches | Survey: *multi-agent systems* |
| **Economics of static context** | Deferred (speaker focus elsewhere) | Google **context caching** (implicit + explicit) | N/A |
| **Stable instructions** | Don’t reset system prompt | Cursor **rules**; Codex **AGENTS.md** | N/A |
| **Evaluation** | **Long-session** turn tests | Vendor long-dialog benchmarks | SWE-ContextBench: bad context **hurts** coding agents |

### Convergence (what leaders and Alex agree on)

- **Context engineering** beats prompt-only tuning ([Karpathy meme](https://youtu.be/esY99nYXxR4) cited in talk; formalized in [survey 2507.13334](https://arxiv.org/abs/2507.13334)).
- **Tool-heavy agents** need policies beyond “send everything” ([Anthropic context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing), [OpenAI trimming cookbook](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory)).
- **Delegate** data-heavy work so the main transcript stays small (Alex sub-agents ≈ Claude Code / multi-agent patterns).
- **Test** long threads before users hit failures (Alex 10→11 evals ≈ production QA ethos in [RhinoInsight](https://arxiv.org/html/2511.18743v1) checklists).

### Divergence (where Alex differs or lags)

| Topic | Alex | Leaders |
|--------|------|---------|
| Summarization | Rejected as primary | Anthropic **compaction** ships server summarization—may work when **controlled** at API layer |
| Long-term memory | In progress | [GitHub Copilot Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory) already targets cross-chat **cited** facts |
| Heuristic | Fixed 100/100 chars | OpenAI **last-N turns**; Anthropic **token triggers** |
| Domain | **Trace/span telemetry** at scale | Copilot/Cursor: **code**; general chat: sessions |

### Recommended hybrid stack (from synthesis JSON)

1. Stable system layer (rules / `AGENTS.md` / unchanged system prompt)  
2. Deterministic trim **or** head/tail + external store (Alex)  
3. Platform tool-result clearing or latest-only tool policy (Anthropic / Alex)  
4. Sub-agents for heavy retrieval (Alex / Claude Code)  
5. **Long-session eval harness** (Alex)  
6. Cross-session memory: Copilot-style citations **or** Mem0/Zep (Alex gap)  
7. Optional API compaction on Claude if you accept server summarization quality  

Source: `results/Comparison_synthesis_Arize_vs_industry.json`.

---

## Per-item pointers (all in `results/*.json`)

### 1. DeLucia / Arize Alex
`DeLucia_talk_video.json` — transcript-backed.

### 2. Anthropic API
`Anthropic_compaction_context_editing.json` — [Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction), [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing).

### 3. Claude Code
`Claude_Code_product.json` — speaker noted similar truncation to Alex; API compaction under the hood.

### 4. OpenAI Agents SDK
`OpenAI_Agents_SDK_context.json` — trimming vs compression; aligns with Alex’s distrust of uncontrolled summarization.

### 5. Google Gemini / ADK
`Google_Gemini_ADK_context.json` — [caching](https://google.github.io/adk-docs/context/caching/), [Vertex overview](https://cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview).

### 6. Cursor IDE
`Cursor_IDE_context.json` — [rules](https://docs.cursor.com/en/context/rules), MCP.

### 7. GitHub Copilot / Microsoft
`GitHub_Copilot_Microsoft_memory.json` — [Copilot Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory), [VS Code agent memory](https://code.visualstudio.com/docs/copilot/agents/memory).

### 8. Survey — Context Engineering
`Survey_context_engineering_2507.json` — [arXiv:2507.13334](https://arxiv.org/abs/2507.13334) (1400+ papers; memory hierarchies + compression taxonomy).

### 9. RhinoInsight
`RhinoInsight_paper.json` — [arXiv:2511.18743](https://arxiv.org/html/2511.18743v1) (checklist + evidence audit vs context rot).

### 10. Memory benchmarks
`Memory_benchmarks.json` — LOCOMO / LongMemEval / DMR (vendor-cited).

### 11–16. Other items
`Mem0.json`, `Zep.json`, `Letta.json`, `OpenAI_sessions.json`, `LangGraph_checkpoints.json`, `Memory_market_landscape.json`.

---

## Validation

```bash
python3 .cursor/skills/deep-research/scripts/validate_json.py \
  -f ai_agent_memory_research/fields.yaml \
  -d ai_agent_memory_research/results
```

**Result:** **17/17 PASS**, 100% average field coverage.
