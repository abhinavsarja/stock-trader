"""Minimal Chainlit + LangChain demo. Run with: `uv run chainlit run chatbot.py`.

Do not use `-w` (watch) unless you expect reload flicker.

Starters omit `icon=` while `/public/` assets are absent (broken icons confuse the UI).

Do not send a message from `@cl.on_chat_start`; that hides starters.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import chainlit as cl
import main.src.trader.graph as graph

load_dotenv()

llm = ChatOpenAI(model=os.getenv("CHATBOT_OPENAI_MODEL", "gpt-4.1-mini"), temperature=0)


@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    return [
        cl.Starter(
            label="Morning routine ideation",
            message=(
                "Can you help me create a personalized morning routine that would help increase "
                "my productivity throughout the day? Start by asking me about my current habits "
                "and what activities energize me in the morning."
            ),
        ),
        cl.Starter(
            label="Explain superconductors",
            message="Explain superconductors like I'm five years old.",
        ),
        cl.Starter(
            label="Python script for daily email reports",
            message=(
                "Write a script to automate sending daily email reports in Python, "
                "and walk me through how I would set it up."
            ),
            # Avoid command="code" — it switches the composer / side panel before you click.
        ),
        cl.Starter(
            label="Text inviting friend to wedding",
            message=(
                "Write a text asking a friend to be my plus-one at a wedding next month. "
                "I want to keep it super short and casual, and offer an out."
            ),
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    """Keep empty: any assistant bubble here hides starter chips."""
    return None


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = (message.content or "").strip()
    if not text:
        return
    await cl.Message(content="Analyzing...").send()

    llm_response = llm.invoke(text)
    content = getattr(llm_response, "content", None) or str(llm_response)
    await cl.Message(content=content).send()
