"""Brave Search API — news results for company / stock context.

Docs: https://api.search.brave.com/res/v1/news/search
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

NEWS_URL = "https://api.search.brave.com/res/v1/news/search"

# Past week, US-focused business news context
_DEFAULT_PARAMS: dict[str, str] = {
    "count": "10",
    "country": "US",
    "search_lang": "en",
    "freshness": "pw",
}


def fetch_news_snippets(query: str, *, count: int = 10) -> str:
    """Return a compact bullet list of recent news headlines + snippets for the LLM.

    If ``BRAVE_API_KEY`` is unset, returns a short configuration hint instead of
    calling the API.
    """
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        return (
            "Brave Search is not configured. Set BRAVE_API_KEY in the environment "
            "(see .env.example)."
        )

    params = {**_DEFAULT_PARAMS, "q": query[:400], "count": str(min(max(count, 1), 20))}
    url = f"{NEWS_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": key,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return f"Brave News API error ({exc.code}): {body}"
    except OSError as exc:
        return f"Brave News request failed: {exc}"

    results = payload.get("results") or []
    if not results:
        topic = query.split("OR")[0].strip() if "OR" in query else query
        return f"No recent news results returned for: {topic}"

    lines: list[str] = []
    for i, item in enumerate(results[: count], start=1):
        title = (item.get("title") or "").strip()
        desc = (item.get("description") or item.get("extra_snippets") or "")
        if isinstance(desc, list):
            desc = desc[0] if desc else ""
        desc = str(desc).strip()[:280]
        age = (item.get("age") or item.get("page_age") or "").strip()
        src_raw = item.get("source")
        if isinstance(src_raw, dict):
            src = (src_raw.get("name") or "").strip()
        elif isinstance(src_raw, str):
            src = src_raw.strip()
        else:
            src = ""
        bit = f"{i}. {title}"
        if age:
            bit += f" ({age})"
        if src:
            bit += f" — {src}"
        lines.append(bit)
        if desc and desc not in title:
            lines.append(f"   {desc}")

    return "\n".join(lines)
