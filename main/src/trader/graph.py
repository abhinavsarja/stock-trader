"""Single-company LangGraph: structured ticker deduction, then Brave + prior-close tools."""

from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .brave_news import fetch_news_snippets
from .state import TraderState
from .stock_quote import normalize_ticker, prior_close_summary

load_dotenv()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)


class TickerDeduction(BaseModel):
    """Structured result of ticker inference — consumed by downstream tools/UI."""

    ticker: str | None = Field(
        default=None,
        description="Exactly one US-listed primary equity symbol if confident, else null.",
    )
    deduction_failed: bool = Field(
        default=False,
        description="True when phrase is ambiguous, non-equity, or confidence is insufficient.",
    )
    user_notice: str = Field(
        description="Brief copy for end users: confirming symbol or explaining what is missing.",
    )
    rejected_raw_ticker: str | None = Field(
        default=None,
        description="If the model guessed a symbol that failed validation, echo it here.",
    )


DEDUCE_SYSTEM = """\
You infer the PRIMARY US-exchange listed stock ticker (NASDAQ/NYSE; common stocks) behind the user's phrase.

Rules:
- If the phrase is ALREADY a plausible symbol alone (e.g. MSFT, GOOGL, BRK.B), normalize mentally to uppercase — set ticker to that symbol and deduction_failed false.
- If it is clearly a widely known issuer with one dominant common ticker (Apple → AAPL), set ticker and deduction_failed false.
- Use deduction_failed true and ticker null when: multiple plausible tickers exist, OTC-only/unknown/private name, ETFs vs stock unclear, conglomerate without clear headline listing, deliberate ambiguity, fictional names, bonds/funds/crypto/forex, or you lack confidence.

user_notice MUST be explicit: either "Using ticker XXX for …" or "Cannot infer ticker because … Provide the exact Yahoo Finance symbol".

Not financial advice. Never invent ticker strings when uncertain.
"""


def deduce_ticker(user_phrase: str, *, config: Any | None = None) -> TickerDeduction:
    structured = llm.with_structured_output(TickerDeduction)
    
    cfg = config if config is not None else {}
    return structured.invoke(
        [
            SystemMessage(content=DEDUCE_SYSTEM),
            HumanMessage(content=f'User phrase: "{user_phrase}"'),
        ],
        config=cfg,
    )


def format_inference_failure(d: TickerDeduction) -> str:
    """Markdown + fenced structured payload for tools / UI retries."""
    payload = d.model_dump()
    json_block = "```ticker_inference\n" + json.dumps(payload, indent=2) + "\n```"

    parts = [
        "### Ticker inference failed",
        "",
        d.user_notice,
        "",
        "**Provide** a Yahoo Finance-compatible US equity symbol next (e.g. `KO`).",
        "",
        json_block,
    ]
    return "\n".join(parts)


@tool
def brave_company_news(company_context: str) -> str:
    """Brave News snippets. Use the user's verbatim company/description string for `company_context`."""
    q = f'{company_context.strip()} stock OR earnings OR analysts'
    return fetch_news_snippets(q, count=12)


@tool
def lookup_previous_close(ticker: str) -> str:
    """Yahoo Finance: prior-session close summary. Requires the structured deduction ticker ONLY (uppercase symbol)."""

    return prior_close_summary(ticker)


def _analysis_system_prompt(*, validated_ticker: str, company_original: str) -> str:
    return f"""You help summarize ONE US-listed stock.

The ticker has ALREADY been inferred and validated upstream as: `{validated_ticker}`.
You MUST call BOTH tools exactly once each:
1. `brave_company_news` with argument `company_context` — copy the text between the <<< and >>> markers verbatim.
2. `lookup_previous_close` with argument `ticker` exactly `{validated_ticker}`

Verbatim phrase for `brave_company_news` (<<<…>>>):
<<<{company_original}>>>

Then reply in compact markdown:
- One line identifying the issuer.
- **Previous close**: numbers only from `lookup_previous_close` — never fabricate prices.
- **Mood**: 2–4 lines inferred only from Brave headlines (bullish/cautious/mixed + why).

Not financial advice."""


def build_analysis_agent(validated_ticker: str, company_original: str) -> object:
    t = validated_ticker.strip().upper()
    prompt = _analysis_system_prompt(validated_ticker=t, company_original=company_original)
    return create_react_agent(llm, tools=[brave_company_news, lookup_previous_close], prompt=prompt)


def run_company_agent(state: TraderState, config) -> TraderState:
    company_original = state.get("company", "").strip()
    if not company_original:
        return {"summary": "Missing company — pass `company` in state."}

    deduction = deduce_ticker(company_original, config=config)

    vt_raw = (deduction.ticker or "").strip() or None
    normalized = normalize_ticker(vt_raw) if vt_raw else None

    success = (not deduction.deduction_failed) and (normalized is not None)
    if success:
        ticker_sym = normalized
        agent_local = build_analysis_agent(ticker_sym, company_original)
        msg = HumanMessage(
            content=(
                f'Do the mandated tool calls then answer for phrase "{company_original}" '
                f"using ticker {ticker_sym}."
            )
        )
        result = agent_local.invoke({"messages": [msg]}, config=config)
        last = result["messages"][-1]
        text = getattr(last, "content", None) or str(last)
        if not isinstance(text, str):
            text = str(text)
        print(f"\n=== {company_original} ===\n{text}")
        return {"summary": text}

    notice = (deduction.user_notice or "").strip() or "Could not infer a valid US ticker."
    if vt_raw and not normalized:
        notice += f" The inferred value `{vt_raw!r}` is not a usable symbol."
    if deduction.deduction_failed and vt_raw is None:
        pass
    elif not deduction.deduction_failed and vt_raw is None:
        notice += " No ticker field was returned."

    inference = TickerDeduction(
        ticker=None,
        deduction_failed=True,
        user_notice=notice,
        rejected_raw_ticker=vt_raw if (vt_raw and not normalized) else None,
    )
    out = format_inference_failure(inference)
    print(f"\n=== {company_original} (inference failed) ===\n{out}")
    return {"summary": out}


def build_graph() -> StateGraph:
    builder = StateGraph(TraderState)
    builder.add_node("analyze", run_company_agent)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder.compile()


graph = build_graph()


def _print_graph_structure() -> None:
    g = graph.get_graph()
    try:
        g.print_ascii()
    except Exception as exc:
        print(f"(ASCII render unavailable: {exc.__class__.__name__})")


if __name__ == "__main__":
    print("Stock Trader (structured ticker → Brave + Yahoo)")
    _print_graph_structure()
    out = graph.invoke({"company": "Apple"})
    print("\n", out.get("summary", ""))
