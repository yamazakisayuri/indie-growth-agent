"""Verify LLM provider selection keeps the Bedrock default (no live model calls).

Run: python scripts/verify_llm_provider.py
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strands import Agent  # noqa: E402
from strands.models.bedrock import BedrockModel  # noqa: E402

from llm import build_model  # noqa: E402

AGENT_MODULES = ("agent.py", "planner.py", "draft_generator.py")


def _agent_calls_missing_model(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Agent"
            and not any(kw.arg == "model" for kw in node.keywords)
        ):
            missing.append(node.lineno)
    return missing


def main() -> None:
    original = os.environ.get("LLM_PROVIDER")
    try:
        # Empty string wins over .env (load_dotenv does not override) → default path.
        os.environ["LLM_PROVIDER"] = ""
        assert build_model() is None
        default_agent = Agent(model=build_model())
        plain_agent = Agent()
        assert isinstance(default_agent.model, BedrockModel), type(default_agent.model)
        assert default_agent.model.get_config() == plain_agent.model.get_config()
        print("OK unset LLM_PROVIDER → Strands default BedrockModel (same config as Agent())")

        for value in ("bedrock", " Bedrock "):
            os.environ["LLM_PROVIDER"] = value
            assert build_model() is None, value
        print("OK LLM_PROVIDER=bedrock (case / whitespace insensitive) → default BedrockModel")

        os.environ["LLM_PROVIDER"] = "no-such-provider"
        try:
            build_model()
        except ValueError as exc:
            assert "no-such-provider" in str(exc), exc
        else:
            raise AssertionError("unknown provider must raise ValueError")
        print("OK unknown LLM_PROVIDER → ValueError")
    finally:
        if original is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = original

    for name in AGENT_MODULES:
        missing = _agent_calls_missing_model(ROOT / name)
        assert not missing, f"{name}: Agent() without model= at lines {missing}"
    print(f"OK every Agent() in {', '.join(AGENT_MODULES)} passes model=build_model()")

    print("\nAll LLM provider checks passed.")


if __name__ == "__main__":
    main()
