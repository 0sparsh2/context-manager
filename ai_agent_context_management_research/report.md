# Deep research report: AI agent context management (2024–2026)

**Methodology.** This report follows the workflow from [Weizhena/Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills): structured outline (`outline.yaml`), typed fields (`fields.yaml`), per-item JSON in `results/`, and validation with `validate_json.py` (10/10 PASS, 100% field coverage). That skill set is explicitly inspired by [RhinoInsight: Improving Deep Research through Control Mechanisms for Model Behavior and Context](https://arxiv.org/html/2511.18743v1)—checklists, staged expansion, and evidence discipline to reduce **context rot** in long research runs.

**As-of date:** 2026-05-14 (see each JSON `last_updated_as_of`).

---

## Table of contents

1. [Anthropic Messages API (caching, compaction, context editing)](#1-anthropic-messages-api-caching-compaction-context-editing) — *Model platform*
2. [Claude Code session and compaction behavior](#2-claude-code-session-and-compaction-behavior) — *Agent product*
3. [Cursor IDE (rules, @ context, MCP host)](#3-cursor-ide-rules--context-mcp-host) — *IDE host*
4. [OpenAI Codex (AGENTS.md, skills, MCP, subagents)](#4-openai-codex-agentsmd-skills-mcp-subagents) — *Agent product*
5. [GitHub Copilot semantic repository indexing](#5-github-copilot-semantic-repository-indexing) — *Platform feature*
6. [Model Context Protocol (MCP)](#6-model-context-protocol-mcp) — *Standard*
7. [Long-context evaluation (NoLiMa, NeedleChain, Haystack-style)](#7-long-context-evaluation-nolima-needlechain-haystack-style) — *Research benchmarks*
8. [SWE-bench family and SWE-ContextBench](#8-swe-bench-family-and-swe-contextbench) — *Coding benchmarks*
9. [Mem0 and long-term memory layers](#9-mem0-and-long-term-memory-layers) — *Infrastructure*
10. [Arize / Sally-Ann DeLucia talk — production agent context](#10-arize--sally-ann-delucia-talk--production-agent-context) — *Industry perspective*

---

## Cross-cutting synthesis

| Layer | What “good” looks like | Representative mechanisms |
|--------|------------------------|---------------------------|
| **API / model host** | Stable prefixes cached; lossy compression only where explicit | [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [compaction](https://platform.claude.com/docs/en/build-with-claude/compaction), [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) |
| **IDE / agent product** | Rules + repo index + subagents; not one giant chat | [Cursor rules](https://docs.cursor.com/en/context/rules), [Copilot indexing](https://docs.github.com/en/copilot/concepts/context/repository-indexing), [Codex customization](https://developers.openai.com/codex/concepts/customization) |
| **Externalized context** | On-demand tools/resources | [MCP specification](https://modelcontextprotocol.io/specification/latest) |
| **Evaluation** | Match benchmark to failure mode | [NoLiMa](https://arxiv.org/html/2502.05167v2), [NeedleChain](https://arxiv.org/html/2507.22411v1), [Haystack-style](https://arxiv.org/html/2510.07414v2), [SWE-ContextBench](https://arxiv.org/html/2602.08316v2) |
| **Long-term memory** | Extract → consolidate → retrieve | [Mem0](https://github.com/mem0ai/mem0), [Mem0 paper](https://arxiv.org/abs/2504.19413) |

**RhinoInsight alignment:** Your research run benefits from the same ideas as the paper: **hierarchical outline** (our `outline.yaml` items), **field schema** (forces comparable notes per item), and **evidence binding** (`primary_sources` in every JSON). Installing the upstream skill pack is optional; the artifacts in `ai_agent_context_management_research/` are self-contained.

---

## Detailed findings (from validated JSON)

### 1. Anthropic Messages API (caching, compaction, context editing)

- **Primitives:** Cache stable prefixes; compaction summarizes and truncates older turns when limits approach; context editing clears tool or thinking blocks for finer token reclamation.
- **Deployment:** Messages API JSON + beta headers per docs.
- **Builder takeaway:** Combine caching for static instructions, context editing for noisy tool dumps, compaction for marathon sessions.

### 2. Claude Code session and compaction behavior

- **Primitives:** Repo- and tool-heavy agent; long sessions depend on compaction-style summarization (mirrors API compaction conceptually).
- **Deployment:** `CLAUDE.md`, CLI/IDE; manual `/compact` where available.
- **Builder takeaway:** Treat compaction as lossy—checkpoint intent in files, not only in chat.

### 3. Cursor IDE (rules, @ context, MCP host)

- **Primitives:** `.cursor/rules` with scoping; `@` context; MCP host.
- **Deployment:** Commit rules; configure MCP servers in Cursor.
- **Builder takeaway:** Many small scoped rules beat one megaprompt; MCP for volatile or sensitive data paths.

### 4. OpenAI Codex (AGENTS.md, skills, MCP, subagents)

- **Primitives:** `AGENTS.md`, skills, memories, MCP, subagents.
- **Deployment:** Repo-local files + host config.
- **Builder takeaway:** Same separation of concerns as RhinoInsight-style control: stable norms vs. reusable procedures vs. external systems.

### 5. GitHub Copilot semantic repository indexing

- **Primitives:** Semantic code index for chat/cloud agent retrieval.
- **Deployment:** Automatic in supported Copilot surfaces; refresh semantics per GitHub docs.
- **Builder takeaway:** RAG-over-repo still needs explicit references for critical edits.

### 6. Model Context Protocol (MCP)

- **Primitives:** Tools, resources, prompts over JSON-RPC.
- **Deployment:** Per-host server configuration with user consent.
- **Builder takeaway:** Prefer on-demand fetch over pasting large blobs into the transcript.

### 7. Long-context evaluation (NoLiMa, NeedleChain, Haystack-style)

- **Primitives:** Controlled long prompts isolating retrieval vs. full-context reasoning vs. agentic noise.
- **Benchmarks:** Use multiple benchmarks—no single needle test proves production readiness.

### 8. SWE-bench family and SWE-ContextBench

- **Primitives:** Real issue fixing; SWE-ContextBench adds **related tasks** and measures reuse of prior context.
- **Finding:** Well-chosen **summarized** context can improve accuracy and cut tokens; **unfiltered** context can hurt ([SWE-ContextBench](https://arxiv.org/html/2602.08316v2)).

### 9. Mem0 and long-term memory layers

- **Primitives:** Extract / consolidate / retrieve memory outside the window.
- **Evidence:** See [arXiv:2504.19413](https://arxiv.org/abs/2504.19413); reproduce claims on your own traces before relying on headline metrics.

### 10. Arize / Sally-Ann DeLucia talk — production agent context

- **Primitives:** Operational framing: context overload, hierarchical memory, observability-first debugging of what enters the prompt.
- **Sources:** [YouTube talk](https://youtu.be/esY99nYXxR4), [Arize blog on context windows](https://arize.com/blog/how-to-manage-llm-context-windows-for-ai-agents/).

---

## Files in this workspace

| Path | Role |
|------|------|
| `deep-research-skills-ref/` | Cloned [Deep-Research-skills](https://github.com/Weizhena/Deep-Research-skills) (reference implementation) |
| `ai_agent_context_management_research/outline.yaml` | Research items + execution config |
| `ai_agent_context_management_research/fields.yaml` | JSON schema for deep phase |
| `ai_agent_context_management_research/results/*.json` | One structured file per item (validated) |
| `.research-venv/` | Local venv used to run `validate_json.py` (PyYAML); safe to delete |

---

## Optional next step (upstream skill install)

To run `/research`, `/research-deep`, and `/research-report` **inside** Claude Code, OpenCode, or Codex, follow the install blocks in the [project README](https://github.com/Weizhena/Deep-Research-skills/blob/master/README.md) (copy skills/agents, enable web search where required, `pip install pyyaml`).
