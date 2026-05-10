from importlib.resources import files

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from .state import TraderState

load_dotenv()

COMPANIES_FILE = (files("main.src.trader") / "data" / "companies.txt")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SYSTEM_PROMPT = (
    "You are a concise financial analyst. "
    "Given a company name, reply with EXACTLY TWO short lines:\n"
    "Line 1: what the company does.\n"
    "Line 2: a notable fact (sector, HQ, ticker, or scale)."
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
    """Ask the LLM for a 2-line description of the current company."""
    company = state["companies"][state["index"]]
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Describe {company}."),
        ]
    )
    description = response.content
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
