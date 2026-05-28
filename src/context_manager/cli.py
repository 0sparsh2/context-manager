from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from context_manager.agent.llm_config import LLMConfig, Provider, load_dotenv_if_present
from context_manager.agent.loop import run_interactive, run_scripted_demo
from context_manager.eval.harness import EvalCase, LongSessionEvaluator
from context_manager.models import Message, TrimMode
from context_manager.session import ContextConfig, ContextSession


def _llm_config_from_args(args: argparse.Namespace) -> LLMConfig:
    provider: Provider = args.llm  # type: ignore[assignment]
    cfg = LLMConfig.from_env(provider=provider)
    if args.model:
        cfg.model = args.model
    if args.api_key:
        cfg.api_key = args.api_key
    if args.base_url:
        cfg.base_url = args.base_url
    return cfg


def cmd_demo(args: argparse.Namespace) -> int:
    cfg = _llm_config_from_args(args)
    if args.interactive:
        run_interactive(llm_config=cfg)
    else:
        run_scripted_demo(verbose=True, llm_config=cfg)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    if not path.exists():
        print(f"Fixture not found: {path}", file=sys.stderr)
        return 1
    case = EvalCase.load(path)
    result = LongSessionEvaluator(case).run()
    print(result.summary())
    return 0 if result.passed else 1


def cmd_eval_all(args: argparse.Namespace) -> int:
    root = Path(args.directory)
    paths = sorted(root.rglob("*.json"))
    if not paths:
        print(f"No fixtures in {root}", file=sys.stderr)
        return 1
    failed = 0
    for path in paths:
        case = EvalCase.load(path)
        result = LongSessionEvaluator(case).run()
        mark = "PASS" if result.passed else "FAIL"
        print(f"[{mark}] {path.relative_to(root)}")
        if not result.passed:
            print(result.summary())
            failed += 1
    print(f"\n{len(paths) - failed}/{len(paths)} passed")
    return 1 if failed else 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Print hot vs full char counts for a fixture replay."""
    case = EvalCase.load(args.fixture)
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode(case.config.get("trim_mode", "head_tail")),
            provider_name=str(case.config.get("provider_name", "mock")),
            keep_last_n=int(case.config.get("keep_last_n", 12)),
            head_messages=int(case.config.get("head_messages", 1)),
            tail_messages=int(case.config.get("tail_messages", 6)),
            tool_policy_enabled=bool(case.config.get("tool_policy_enabled", True)),
            recall_require_verified=bool(case.config.get("recall_require_verified", False)),
            recall_max_age_seconds=int(case.config.get("recall_max_age_seconds", 60 * 60 * 24 * 14)),
        )
    )
    try:
        for turn in case.turns:
            for raw in turn:
                session.append(Message.from_dict(raw))
        hot = session.get_hot_context()
        print(f"turns: {len(case.turns)}")
        print(f"full messages: {len(session.messages)}  chars: {session.total_chars()}")
        print(f"hot messages: {len(hot)}  chars: {session.hot_char_count()}")
        print(f"archived segments: {len(session.list_archived_segments())}")
        if args.verbose:
            for i, m in enumerate(hot):
                preview = m.content[:120].replace("\n", " ")
                print(f"  [{i}] {m.role}: {preview}")
    finally:
        session.close()
    return 0


def cmd_diag(args: argparse.Namespace) -> int:
    case = EvalCase.load(args.fixture)
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode(case.config.get("trim_mode", "head_tail")),
            provider_name=str(case.config.get("provider_name", "mock")),
            keep_last_n=int(case.config.get("keep_last_n", 12)),
            head_messages=int(case.config.get("head_messages", 1)),
            tail_messages=int(case.config.get("tail_messages", 6)),
            tool_policy_enabled=bool(case.config.get("tool_policy_enabled", True)),
            recall_require_verified=bool(case.config.get("recall_require_verified", False)),
            recall_max_age_seconds=int(case.config.get("recall_max_age_seconds", 60 * 60 * 24 * 14)),
        )
    )
    try:
        for turn in case.turns:
            for raw in turn:
                session.append(Message.from_dict(raw))
        compaction = session.compaction_diagnostics()
        recalls = [session.recall_diagnostics(seg.id) for seg in session.list_archived_segments()[: args.limit]]
        if args.json:
            payload = {
                "compaction_trace": compaction,
                "recall_traces": recalls,
            }
            print(json.dumps(payload, indent=2 if not args.compact else None))
            return 0

        print("compaction_trace:")
        print(json.dumps(compaction, indent=2))
        for rec in recalls:
            seg_id = rec.get("segment_id", "?")
            print(f"\nrecall_trace segment={seg_id}")
            print(json.dumps(rec, indent=2))
    finally:
        session.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(prog="context-manager", description="Context Manager MVP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("eval", help="Run long-session eval fixture")
    p_eval.add_argument("fixture", type=str, help="Path to JSON eval case")
    p_eval.set_defaults(func=cmd_eval)

    p_all = sub.add_parser("eval-all", help="Run all JSON fixtures in a directory")
    p_all.add_argument(
        "directory",
        type=str,
        nargs="?",
        default="fixtures",
        help="Fixture root (default: fixtures)",
    )
    p_all.set_defaults(func=cmd_eval_all)

    p_demo = sub.add_parser("demo", help="Run minimal agent loop with context session")
    p_demo.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive REPL instead of scripted demo",
    )
    p_demo.add_argument(
        "--llm",
        choices=["mock", "openai", "nim"],
        default="mock",
        help="LLM provider (default: mock). nim = NVIDIA NIM OpenAI-compatible API",
    )
    p_demo.add_argument("--model", type=str, default=None, help="Model id (e.g. meta/llama-3.1-8b-instruct)")
    p_demo.add_argument("--api-key", type=str, default=None, help="API key (else env: NVIDIA_API_KEY / OPENAI_API_KEY)")
    p_demo.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="OpenAI-compatible base URL (nim default: https://integrate.api.nvidia.com/v1)",
    )
    p_demo.set_defaults(func=cmd_demo)

    p_inspect = sub.add_parser("inspect", help="Replay fixture and print context stats")
    p_inspect.add_argument("fixture", type=str)
    p_inspect.add_argument("-v", "--verbose", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect)

    p_diag = sub.add_parser("diag", help="Print recall + compaction diagnostics for a fixture")
    p_diag.add_argument("fixture", type=str)
    p_diag.add_argument("--limit", type=int, default=3, help="Max archived segments to inspect")
    p_diag.add_argument("--json", action="store_true", help="Emit combined diagnostics as JSON")
    p_diag.add_argument("--compact", action="store_true", help="Use compact JSON (single-line) with --json")
    p_diag.set_defaults(func=cmd_diag)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
