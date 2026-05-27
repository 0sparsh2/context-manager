# Reliability Plus Competitive Gap Closure Plan

Context: `main` branch, repository `context-manager`  
Posture: SELECTIVE EXPANSION (keep reliability-first core, add high-leverage gap closure)  
Date: 2026-05-27

## Objective
Evolve the existing reliability-first plan into a competitively credible plan that closes the highest strategic gaps (cross-session memory, benchmark rigor, verification, operability) without inflating scope into a platform rewrite.

## NOT in Scope
- Building a full web UI or hosted control plane.
- Multi-tenant auth, billing, and SaaS account management.
- Production-grade temporal knowledge graph implementation this cycle.
- Full MCP server feature expansion beyond planning hooks.
- Replacing the deterministic trim/tool policies already working in `src/context_manager/policies`.

## What Already Exists (Reuse Map)
- **Core session orchestration:** `src/context_manager/session.py` (trim/archive/recall flow).
- **Policy layer:** `src/context_manager/policies/trim.py`, `src/context_manager/policies/tools.py`.
- **Persistence baseline:** `src/context_manager/store/sqlite.py` (warm archive primitives).
- **Agent loop + adapters:** `src/context_manager/agent/loop.py`, `src/context_manager/agent/openai_adapter.py`, `src/context_manager/agent/llm_factory.py`.
- **Error baseline:** `src/context_manager/errors.py`.
- **Evaluation harness:** `src/context_manager/eval/harness.py`.
- **Operational entrypoints:** `src/context_manager/cli.py`, repo workflows.

## Dream State Delta
Current state is strong deterministic in-session control but weak long-horizon memory, verification, and measurable SLO gates.  
Target state keeps current deterministic strengths and adds:
1. Pluggable provider compaction abstraction with deterministic fallback.
2. Optional cross-session semantic memory backend behind flags.
3. Retrieval verification/freshness checks before memory injection.
4. Benchmark-backed CI gates (quality + latency + cost).
5. Unified error taxonomy + rescue behavior + telemetry traces.

---

## Section 1 — Problem Framing and Scope Control
### Findings
- Reliability hardening is correct but incomplete versus competitor baseline; strategic gaps remain in memory durability and eval rigor.
- Scope creep risk is high if semantic memory, governance, and UX are tackled as one bundle.

### Decision
- Keep reliability-first foundations as mandatory P0.
- Add only high-leverage competitive closures that can be isolated behind interfaces/feature flags.

### Scope Guardrails
- No backend service split.
- No new persistent infrastructure hard dependency for default path.
- Every new capability must degrade to current deterministic behavior.

---

## Section 2 — Architecture and Boundary Review
### Findings
- Existing boundaries (`session`, `store`, `agent`, `eval`) are suitable for selective expansion.
- Memory and compaction capabilities are currently implicit/provider-specific and need explicit interfaces.

### Revised Architecture Moves
- Add `MemoryBackend` abstraction in `src/context_manager/store/` (e.g., `memory_backend.py`) with `none` and pilot adapter implementations.
- Add `CompactionStrategy` abstraction in `src/context_manager/agent/` to encapsulate provider-specific compaction/editing support.
- Keep `ContextSession` as orchestrator; inject interfaces via config.

### Acceptance Signal
- Existing public flows run unchanged when new flags are disabled.

---

## Section 3 — Data and State Model Review
### Findings
- Current archive supports deterministic recall primitives but no semantic index contract or recall provenance fields.
- No first-class notion of recall confidence, freshness, or citation linkage.

### Plan
- Extend recall result model in `src/context_manager/models.py` with optional metadata:
  - `source_segment_ids`
  - `retrieval_method` (`id`, `keyword`, `semantic`)
  - `confidence`
  - `freshness_state`
  - `verification_state`
- Keep SQLite schema evolution additive and backward compatible.

### Acceptance Signal
- Reads old records safely; new metadata fields are optional and nullable.

---

## Section 4 — API/Contract and Compatibility Review
### Findings
- Error and status semantics are inconsistent across adapter/session/tool pathways.
- Competitive parity needs explicit capability detection and deterministic fallback contracts.

### Plan
- Standardize internal status enums and error codes at boundaries.
- Add capability probes in adapter/config layer:
  - compaction available/unavailable
  - semantic memory backend enabled/disabled
- Emit compatibility-safe output; enrich with metadata instead of breaking message shape.

### Acceptance Signal
- Existing tests for user-facing tool outputs still pass while metadata expands.

---

## Section 5 — Reliability, Failure Handling, and Recovery
### Error & Rescue Registry
| Code | Trigger | Rescue | User/Operator Guidance |
|---|---|---|---|
| `E_STORE_IO` | SQLite read/write error | retry (bounded) then fail mapped | surface storage path and retry hint |
| `E_SEGMENT_NOT_FOUND` | missing recall segment | deterministic not-found status | suggest keyword/semantic fallback |
| `E_LLM_TIMEOUT` | provider timeout | bounded retry with jitter | note timeout budget exceeded |
| `E_LLM_AUTH` | auth/permission error | fail-fast no retry | actionable env/config message |
| `E_LLM_PROVIDER` | non-timeout provider failure | one retry if transient | provider-specific diagnostics |
| `E_COMPACTION_UNAVAILABLE` | provider lacks feature | fallback to deterministic trim | explain degraded mode |
| `E_MEMORY_BACKEND_UNAVAILABLE` | backend misconfig/outage | fallback to archive-only recall | continue without semantic memory |
| `E_RECALL_VERIFICATION_FAILED` | stale/unverified memory | block injection by policy | prompt for revalidation path |

### Failure Modes Table (Critical Gaps Highlighted)
| Failure mode | Current rescue | Gap severity | Critical gap | Target rescue |
|---|---|---|---|---|
| Cross-session semantic recall absent | keyword/id only | Critical | Yes | feature-flagged semantic backend |
| Recalled fact may be stale/unverified | none | Critical | Yes | verification/freshness policy gate |
| Benchmark regressions merge silently | ad-hoc checks | Critical | Yes | CI benchmark thresholds |
| Compaction behavior varies by provider | implicit behavior | High | Yes | explicit strategy + fallback |
| Memory telemetry missing | limited hooks | High | Yes | recall/compaction counters + latency |
| Store/provider errors inconsistent | mixed tracebacks/strings | High | No | unified registry + mapping |
| Recall scans degrade with scale | mostly linear | Medium | No | bounded scans + perf budget alerts |

---

## Section 6 — Security, Privacy, and Governance Review
### Findings
- Plan currently mentions telemetry but not privacy guardrails on recalled memory.
- Competitive baselines emphasize memory governance and validation.

### Plan
- Add namespace scoping hooks in memory interfaces.
- Add optional redaction callback in `ContextConfig`.
- Add TTL policy support for memory backend records.
- Ensure telemetry omits sensitive raw content by default.

### Acceptance Signal
- Unit tests verify redaction hook is applied before emit/persist operations.

---

## Section 7 — Performance and Scalability Review
### Findings
- Current performance checks are narrow (char ratio + spot latency).
- No gated p95 latency/token-cost budgets per policy path.

### Plan
- Extend `src/context_manager/eval/harness.py` with benchmark slices:
  - lost-in-the-middle
  - recall precision/recall-at-k
  - token delta per policy
  - p50/p95 latency per turn
- Add configurable scan caps and memory backend query budgets.

### Acceptance Signal
- CI fails when regression exceeds explicit thresholds.

---

## Section 8 — Observability and Operational Readiness Review
### Findings
- Current observability is insufficient for diagnosing memory/compaction behavior under load.

### Plan
- Expand telemetry events with stable schema:
  - `memory.recall_attempt`, `memory.recall_hit`, `memory.recall_miss`
  - `memory.verification_pass`, `memory.verification_block`
  - `compaction.applied`, `compaction.fallback`
  - `policy.token_budget`
- Produce machine-readable eval artifacts for CI trend comparison.

### Acceptance Signal
- No-op sink remains side-effect-free; debug sink output is deterministic in tests.

---

## Section 9 — Developer Experience and Integration Review
### Findings
- CLI/library paths are strong for engineers but lack inspectability for memory decisions.

### Plan
- Add CLI inspection commands in `src/context_manager/cli.py`:
  - recall diagnostics (why this memory was selected)
  - feature capability status (compaction/backend availability)
- Add integration docs for LangGraph/Redis and MCP wrapper usage without mandatory dependency adoption.

### Acceptance Signal
- CLI docs + examples demonstrate diagnosis of at least one blocked verification and one fallback path.

---

## Section 10 — Delivery Plan, Dependencies, and Sequencing
### Prioritized Implementation Tasks (with explicit acceptance criteria)
1. **Unified error taxonomy and mapping**  
   - Targets: `src/context_manager/errors.py`, `src/context_manager/agent/openai_adapter.py`, `src/context_manager/session.py`  
   - Acceptance: all mapped codes emitted; no raw provider traceback leaks in normal execution paths.
2. **Capability-aware compaction strategy interface**  
   - Targets: `src/context_manager/agent/llm_factory.py`, new `src/context_manager/agent/compaction.py`, `src/context_manager/agent/types.py`  
   - Acceptance: strategy selection logged; unsupported providers trigger deterministic fallback with `E_COMPACTION_UNAVAILABLE`.
3. **Memory backend abstraction + none/mem0 pilot adapter**  
   - Targets: new `src/context_manager/store/memory_backend.py`, `src/context_manager/store/__init__.py`, `src/context_manager/session.py`  
   - Acceptance: flag-off path unchanged; flag-on pilot path passes integration fixtures.
4. **Recall verification and freshness policy gate**  
   - Targets: `src/context_manager/session.py`, `src/context_manager/models.py`, `src/context_manager/policies/tools.py`  
   - Acceptance: unverified/stale recalls are blocked or downgraded per policy; decision reason is recorded.
5. **Benchmark harness expansion and score artifact generation**  
   - Targets: `src/context_manager/eval/harness.py`, fixtures under `fixtures/`  
   - Acceptance: benchmark JSON artifact includes recall/latency/token metrics and uncertainty tags.
6. **CI benchmark and reliability gates**  
   - Targets: `.github/workflows/` (fast + benchmark/nightly pipelines), `README.md` badges/docs  
   - Acceptance: PR gate enforces configured thresholds; nightly publishes benchmark artifacts.
7. **Operational telemetry schema extension**  
   - Targets: `src/context_manager/session.py`, `src/context_manager/agent/loop.py`, config/docs  
   - Acceptance: required telemetry events emitted with stable keys; no-op mode preserves zero side effects.
8. **CLI diagnostics for recall/compaction decisions**  
   - Targets: `src/context_manager/cli.py`, `README.md` usage docs  
   - Acceptance: operator can inspect why memory was selected, verified, blocked, or fallback-applied.

### Sequence
- **Wave 1 (P0):** tasks 1, 2, 5, 6 (foundational reliability + measurable gates).
- **Wave 2 (P1):** tasks 3, 4, 7 (competitive memory closure with controls).
- **Wave 3 (P2):** task 8 (operator ergonomics).

### Unresolved Items
- Final backend selection after pilot benchmark comparison (Mem0 vs Redis/LangGraph profile).
- Freshness heuristics calibration per workload domain.

---

## Section 11 — UI/UX Surface Review
Skipped: no standalone product UI scope is approved for this cycle; only CLI/operator diagnostics are included to avoid scope expansion beyond selective engineering closure.

---

## ENG REVIEW REPORT

| Field | Value |
|---|---|
| skill | plan-eng-review |
| mode | auto / selective_expansion |
| status | completed_with_open_decisions |
| core_scope_preserved | yes |
| competitive_gap_closure_added | yes |
| unresolved | backend finalization; freshness heuristic calibration |
| critical_gaps | cross-session semantic memory; recall verification/freshness; benchmark CI gates; capability-aware compaction; memory observability |
| verdict | Proceed with Wave 1 immediately; gate Wave 2 on benchmark evidence and fallback quality. |
