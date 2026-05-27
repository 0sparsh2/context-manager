# Reliability First Engineering Plan

Context: `main` branch, repository `context-manager`
Mode: SELECTIVE EXPANSION
Date: 2026-05-27

## Step 0

### Premise Challenge
1. The highest near-term risk is not feature depth, but operational reliability under real traffic and slow model backends.
2. Current implementation is correct for MVP behavior, but error semantics are inconsistent across boundaries.
3. Shipping MCP and wider adoption before reliability hardening will create noisy bug reports and slow integration.

### Code Leverage
- Reuse existing clean boundaries: `session`, `store`, `agent`, `eval`.
- Preserve the current policy behavior and fixture suite as behavioral guardrails.
- Add reliability layers without changing public mental model.

### Dream State
CURRENT STATE -> THIS PLAN -> 12-MONTH IDEAL

- Current: deterministic trim/archive/recall + solid tests
- This plan: typed failures, metrics, CI tiers, bounded retries and runbooks
- 12-month ideal: production-ready middleware with MCP surface and confidence dashboards

### Implementation Alternatives

#### A) Reliability Core (recommended)
- Add typed exception model and explicit error results at store/session/adapter boundaries
- Add metrics hooks and structured events
- Add CI split (fast required, slow optional/nightly)

Effort: M
Risk: Low
Pros: Largest trust gain per week
Cons: Less visible than major new features

#### B) Distribution-First
- Build MCP first, harden reliability after external usage

Effort: M
Risk: Medium
Pros: Faster adoption loop
Cons: Externalizes reliability costs to users

#### C) Scale-First Retrieval
- Invest in indexing/semantic recall and high-volume tuning now

Effort: L
Risk: Medium-High
Pros: Better long-run throughput
Cons: Premature before reliability semantics are stable

Recommendation: A

## Deep Engineering Findings and Improvements

### 1) Error & Rescue Map

#### Findings
- Store errors (`sqlite3`) are not wrapped in domain errors.
- `recall()` returns `None` for not-found while tool execution returns string `"ERROR: ..."` for similar classes of problems.
- Network failures and timeout failures bubble from adapter without normalized classification.

#### Improvement Plan
- Introduce typed error classes:
  - `ContextManagerError` (base)
  - `StoreError`, `SegmentNotFoundError`
  - `LLMProviderError`, `LLMTimeoutError`, `LLMAuthError`
- Introduce deterministic error mapping in adapter:
  - OpenAI/NIM timeout -> `LLMTimeoutError`
  - auth/permission -> `LLMAuthError`
  - other API failures -> `LLMProviderError`
- Unify tool result handling:
  - internal methods return `(content, status)` where status is enum (`ok`, `not_found`, `failed`)
  - convert to user-facing tool output in one place
- Keep current external behavior for compatibility in v1, but add `metadata.error_code` on error tool messages.

#### Validation
- New tests for each mapped exception class.
- Regression test for compatibility output text.

---

### 2) Observability

#### Findings
- No counters/traces for:
  - hot/full ratio
  - archive writes
  - recall latency and hit rate
  - provider timeout/retry rates
- Hard to diagnose regressions outside local debugging.

#### Improvement Plan
- Add lightweight telemetry hook interface:
  - `TelemetrySink.record(event_name, fields)`
  - No-op default implementation
- Emit events:
  - `context.trim_applied`
  - `context.segment_archived`
  - `context.recall_attempt`
  - `llm.request`
  - `llm.error`
- Keep implementation dependency-free; allow user-provided adapters (logs, OTEL, StatsD) later.
- Add CLI flag for verbose telemetry in demos (`--telemetry-debug`).

#### Validation
- Snapshot tests on emitted telemetry fields.
- Ensure no telemetry side effects when sink is no-op.

---

### 3) Deployment & CI

#### Findings
- No GitHub workflow currently enforces baseline quality.
- NIM live tests are long-running and unsuitable for required PR gate.

#### Improvement Plan
- Add two-tier CI:
  1. `ci-fast.yml` (required): lint, unit tests, fixture evals
  2. `ci-live-nim.yml` (manual or nightly): deep NIM integration phases
- Archive phase outputs as build artifacts.
- Add badges in README for fast and nightly workflows.

#### Validation
- Verify green runs on clean clone.
- Introduce one intentional failing test to confirm fast gate blocks merges.

---

### 4) Performance (Targeted Reliability)

#### Findings
- `recall_by_keyword` scans all segments linearly.
- Works at current scale but uncertain at 10k+ segments per session.

#### Improvement Plan
- Add optional bounded recall search:
  - newest-first scan and configurable cap (`max_segments_scan`)
- Add index support for session + position already present, keep this path simple for v1.
- Expose recall scan metrics to detect future scale pain.

#### Validation
- Perf micro-benchmark around segment scan counts.
- Assert stable behavior under cap fallback semantics.

## NOT in Scope (this cycle)
- Semantic vector retrieval
- Full Mem0/Zep integration
- Anthropic-style server compaction
- MCP server feature surface expansion
- Product analytics dashboards

## Error Registry (proposed)
- `E_STORE_IO`
- `E_SEGMENT_NOT_FOUND`
- `E_LLM_TIMEOUT`
- `E_LLM_AUTH`
- `E_LLM_PROVIDER`
- `E_TOOL_EXECUTION`

## Failure Modes Table

| Failure mode | Current rescue | User-visible | Target rescue |
|---|---|---|---|
| SQLite write/read failure | uncaught exception | traceback | mapped `StoreError`, deterministic tool/system message |
| Segment not found | `None` or string error | inconsistent | `E_SEGMENT_NOT_FOUND` unified response |
| LLM timeout | uncaught provider exception | traceback | `E_LLM_TIMEOUT` + bounded retry policy |
| LLM auth failure | uncaught provider exception | traceback | `E_LLM_AUTH` with actionable env guidance |
| Recall scan too large | full scan | latent slowness | cap + telemetry + warning |

## Implementation Tasks
- [ ] Add error class module and typed mapping layer
- [ ] Refactor adapter error translation and timeout handling
- [ ] Add status enum for tool execution path
- [ ] Add telemetry sink interface and no-op default
- [ ] Emit telemetry from session/store/adapter/loop
- [ ] Add fast CI workflow
- [ ] Add nightly/manual NIM workflow
- [ ] Add benchmark for recall scan and cap behavior
- [ ] Update README reliability and operations section

## ENG REVIEW REPORT

| Review | Status | Findings |
|--------|--------|----------|
| Eng Review | issues_open | reliability hardening required before broader distribution |

VERDICT: Reliability First plan is ready for implementation after user approval.
