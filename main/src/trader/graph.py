from importlib.resources import files

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from .state import TraderState

load_dotenv()

COMPANIES_FILE = files("main.src.trader") / "data" / "companies.txt"
PREFERRED_FILE = files("main.src.trader") / "data" / "preferred_companies.txt"


def _load_preferred() -> set[str]:
    text = PREFERRED_FILE.read_text(encoding="utf-8")
    return {line.strip().lower() for line in text.splitlines() if line.strip()}


_PREFERRED = _load_preferred()

_TREND_TABLE: dict[str, dict] = {
    "apple":     {"ticker": "AAPL",  "price": 232.10, "change_1d_pct":  0.8, "change_30d_pct":  4.2, "trend": "uptrend"},
    "microsoft": {"ticker": "MSFT",  "price": 421.55, "change_1d_pct": -0.3, "change_30d_pct":  2.1, "trend": "neutral"},
    "nvidia":    {"ticker": "NVDA",  "price": 138.75, "change_1d_pct":  1.4, "change_30d_pct":  9.6, "trend": "strong-uptrend"},
    "tesla":     {"ticker": "TSLA",  "price": 248.30, "change_1d_pct": -1.1, "change_30d_pct": -3.4, "trend": "downtrend"},
    "alphabet":  {"ticker": "GOOGL", "price": 165.20, "change_1d_pct":  0.4, "change_30d_pct":  1.8, "trend": "neutral"},
}


@tool
def is_preferred(company: str) -> bool:
    """Check whether the user has marked this company as preferred.

    Call this only for companies you have determined to be in the TECHNOLOGY
    sector, before deciding whether to fetch stock trends.
    """
    return company.strip().lower() in _PREFERRED


@tool
def get_stock_trend(company: str) -> str:
    """Return the latest stock price and trend for a company.

    Only call this for companies the user has marked as preferred. Returns
    ticker, price, 1-day and 30-day change percentages, and a trend label.
    """
    data = _TREND_TABLE.get(company.strip().lower())
    if not data:
        return f"No trend data available for {company}."
    return (
        f"{data['ticker']} @ ${data['price']:.2f} "
        f"({data['change_1d_pct']:+.1f}% 1d, "
        f"{data['change_30d_pct']:+.1f}% 30d) — {data['trend']}"
    )


SYSTEM_PROMPT = (
    "You are a concise financial analyst. For each company you receive:\n"
    "1. Use your own knowledge to decide whether the company is in the TECHNOLOGY sector.\n"
    "2. If it IS technology, call `is_preferred` to check whether the user has marked it as preferred.\n"
    "3. If `is_preferred` returns true, call `get_stock_trend` and include the trend in your answer.\n"
    "\n"
    "Output rules:\n"
    "- Preferred technology companies: 4 short lines — what they do, a notable fact, "
    "the current stock trend (verbatim from the tool), and a one-line outlook.\n"
    "- Everything else: exactly 2 short lines — what they do, and a notable fact.\n"
    "\n"
    "Do not call any tools for non-technology companies."
)


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_react_agent(
    llm,
    tools=[is_preferred, get_stock_trend],
    prompt=SYSTEM_PROMPT,
)


def load_companies(state: TraderState) -> TraderState:
    """Read the company list from disk and reset the cursor."""
    text = COMPANIES_FILE.read_text(encoding="utf-8")
    companies = [line.strip() for line in text.splitlines() if line.strip()]

    if not companies:
        raise ValueError(
            f"No companies found in {COMPANIES_FILE.name}. "
            "Add at least one company name (one per line)."
        )

    print(f"Loaded {len(companies)} companies from {COMPANIES_FILE.name}")
    return {"companies": companies, "index": 0, "descriptions": {}}


def describe_company(state: TraderState) -> TraderState:
    """Run a per-company ReAct agent that may call is_preferred / get_stock_trend."""
    company = state["companies"][state["index"]]
    result = agent.invoke(
        {"messages": [HumanMessage(content=f"Describe {company}.")]}
    )
    description = result["messages"][-1].content
    print(f"\n=== {company} ===\n{description}")
    return {
        "descriptions": {**state["descriptions"], company: description},
        "index": state["index"] + 1,
    }


def has_more_companies(state: TraderState) -> str:
    """Conditional router: keep looping until every company is described."""
    if state["index"] < len(state["companies"]):
        return "describe"
    return "done"


def build_graph():
    """Build the stock trader graph."""
    builder = StateGraph(TraderState)
    builder.add_node("load", load_companies)
    builder.add_node("describe", describe_company)

    builder.add_edge(START, "load")
    builder.add_edge("load", "describe")
    builder.add_conditional_edges(
        "describe",
        has_more_companies,
        {"describe": "describe", "done": END},
    )
    return builder.compile()


graph = build_graph()


def _print_graph_structure() -> None:
    """ASCII render the graph; fall back to listing edges if grandalf chokes."""
    g = graph.get_graph()
    try:
        g.print_ascii()
    except Exception as exc:
        print(f"(ASCII render unavailable: {exc.__class__.__name__})")
        print("Nodes:", ", ".join(g.nodes))
        print("Edges:")
        for edge in g.edges:
            arrow = "..>" if getattr(edge, "conditional", False) else "-->"
            print(f"  {edge.source} {arrow} {edge.target}")


if __name__ == "__main__":
    print("Stock Trader initialized.")
    print("Graph structure:")
    _print_graph_structure()

    result = graph.invoke({"companies": [], "index": 0, "descriptions": {}})

    print("\n=== Summary ===")
    for company, desc in result["descriptions"].items():
        print(f"\n{company}:\n{desc}")
