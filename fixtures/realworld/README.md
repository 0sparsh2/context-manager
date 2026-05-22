# Real-world scenario fixtures

| Fixture | Models | What it tests |
|---------|--------|----------------|
| `arize_observability_turn11.json` | Arize Alex / Phoenix | Trace search tool spam, turn-11 recall of original `trace_id`, warm store for old spans |
| `cursor_coding_agent.json` | Cursor / Codex | Many `read_file`/`grep` tools, follow-up about earlier `KEY_FINDING` |
| `openai_support_last_n.json` | OpenAI Agents SDK | `last_n` trim (not head/tail), support thread, recall early email |
| `subagent_delegation.json` | Alex sub-agents | Parent thread **only** gets `SUBAGENT_RESULT` (no raw sub-agent tool in parent) |

Programmatic stress tests (no JSON): `tests/test_realworld_simulations.py`

- 20× span dumps (~3.5k chars each) — latest hot, first recallable  
- DeLucia exact 10 filler turns → turn 11 `PRIMARY_GOAL`  
- 50× `read_file` — recall `FILE_CHUNK_003`  
- Compression ratio hot &lt; 50% of full after 30× 5k tool outputs  

Run all:

```bash
./scripts/run_realworld_suite.sh
# or
pytest -q
context-manager eval-all fixtures
```
