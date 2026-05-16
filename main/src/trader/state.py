from typing import TypedDict


class TraderState(TypedDict, total=False):
    """Shared state between the two agents in the graph."""

    company: str
    # After agent 1 (ticker inference — structured output)
    inference_ok: bool
    validated_ticker: str | None
    # Final user-facing markdown from either agent 1 (failure) or agent 2 (success)
    summary: str
