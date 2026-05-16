"""Chainlit chat UI for the stock-trader LangGraph.

Run with:
    uv run chainlit run app.py
"""

from __future__ import annotations

import re

import chainlit as cl

from main.src.trader.email_sender import send_email_via_mcp
from main.src.trader.graph import graph


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    """Shown in the composer on an empty thread. Only registered when running `chainlit run app.py`."""
    return [
        cl.Starter(label="Apple", message="Apple"),
        cl.Starter(label="Ticker NVDA", message="NVDA"),
        cl.Starter(label="Microsoft", message="Microsoft"),
        cl.Starter(label="Alphabet", message="Alphabet"),
    ]


@cl.on_chat_start
async def start() -> None:
    """Do not send an assistant bubble here — that hides starters and triggers the generic greeting UX.

    Onboarding lives in `/chainlit.md` (readme) instead.
    """
    return None


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Run analysis for the company/ticker in the message text."""
    text = (message.content or "").strip()
    if not text:
        await cl.Message("Enter a company name or stock symbol (e.g. `NVDA`).").send()
        return

    await analyze_company(text)


async def analyze_company(company: str) -> None:
    """Run LangGraph for one company; stream callbacks; offer email."""
    await cl.Message(f"Analyzing **{company}**…").send()

    callback = cl.LangchainCallbackHandler()
    summary = ""

    try:
        async for chunk in graph.astream(
            {"company": company},
            config={"callbacks": [callback]},
        ):
            data = chunk.get("analyze") if isinstance(chunk, dict) else None
            if isinstance(data, dict) and data.get("summary"):
                summary = data["summary"]
    except Exception as exc:
        await cl.Message(f"Error while analyzing: `{exc.__class__.__name__}: {exc}`").send()
        return

    if summary:
        await cl.Message(content=summary).send()
        report = f"# {company}\n\n{summary}"
        await cl.Message("Done.").send()
        await _offer_email(report, company)
    else:
        await cl.Message("No summary was produced.").send()


async def _offer_email(report: str, company: str) -> None:
    """Prompt for an email address and send the report via the Resend MCP server."""
    res = await cl.AskUserMessage(
        content="Want this emailed? Enter an address (or type `skip`):",
        timeout=180,
    ).send()

    addr = ((res or {}).get("output") or "").strip()
    if not addr or addr.lower() == "skip":
        return

    if not _EMAIL_RE.match(addr):
        await cl.Message(
            f"`{addr}` doesn't look like a valid email — skipping."
        ).send()
        return

    subject = f"Stock summary — {company}"

    async with cl.Step(name="Send email via MCP Resend", type="tool") as step:
        step.input = {"to": addr, "subject": subject}
        try:
            step.output = await send_email_via_mcp(
                to=addr,
                subject=subject,
                text=report,
            )
        except Exception as exc:
            step.output = f"{exc.__class__.__name__}: {exc}"
            await cl.Message(f"Email failed: `{exc}`").send()
            return

    await cl.Message(f"Sent the report to **{addr}**.").send()
