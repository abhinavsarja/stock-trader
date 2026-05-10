"""Entry point for the stock-trader application."""

from __future__ import annotations

import os
from dotenv import load_dotenv


def main() -> None:
    """Initialize environment and run the stock trader agent."""
    load_dotenv()

    openai_key_present = bool(os.getenv("OPENAI_API_KEY"))

    print("Stock Trader initialized.")
    print(f"OPENAI_API_KEY loaded: {openai_key_present}")


if __name__ == "__main__":
    main()
