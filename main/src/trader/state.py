from typing import TypedDict


class TraderState(TypedDict):
    """Shared state passed between nodes in the stock trader graph."""

    companies: list[str]
    index: int
    descriptions: dict[str, str]
