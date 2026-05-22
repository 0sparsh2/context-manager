"""Context Manager — session policies, warm store, and eval harness."""

from context_manager.agent.llm_config import LLMConfig
from context_manager.agent.llm_factory import create_llm
from context_manager.agent.loop import AgentTurnResult, MinimalAgentLoop, run_scripted_demo
from context_manager.eval.harness import EvalCase, EvalResult, LongSessionEvaluator
from context_manager.models import Message, Segment, TrimMode
from context_manager.session import ContextConfig, ContextSession

__version__ = "0.1.0"

__all__ = [
    "AgentTurnResult",
    "LLMConfig",
    "create_llm",
    "Message",
    "MinimalAgentLoop",
    "Segment",
    "TrimMode",
    "ContextConfig",
    "ContextSession",
    "EvalCase",
    "EvalResult",
    "LongSessionEvaluator",
    "run_scripted_demo",
]
