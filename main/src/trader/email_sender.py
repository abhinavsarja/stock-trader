"""Send email via the `mcp-resend-email` MCP server, spawned per call over stdio.

The server is started with::

    mcp-resend-email --api-key=$RESEND_API_KEY

For each call we open a fresh `stdio_client` + `ClientSession`, discover the
send-email tool by name match (the third-party package's tool name is not
documented), invoke it, and tear the subprocess down.

Required env vars:
    RESEND_API_KEY     - Resend API key
    RESEND_FROM_EMAIL  - Verified sender address on a Resend-verified domain

Optional env var:
    MCP_RESEND_EMAIL_CMD  - Override path to the mcp-resend-email binary.
                            Defaults to `mcp-resend-email` (must be on PATH).
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent


_SEND_TOOL_RE = re.compile(r"send.*email|email.*send", re.IGNORECASE)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is not set. "
            f"Add it to your .env file (see .env.example)."
        )
    return value


async def _find_send_tool(session: ClientSession) -> str:
    """Locate the send-email tool by name on the connected MCP server."""
    listed = await session.list_tools()
    for tool in listed.tools:
        if _SEND_TOOL_RE.search(tool.name):
            return tool.name
    names = ", ".join(t.name for t in listed.tools) or "<none>"
    raise RuntimeError(
        f"mcp-resend-email exposed no send-email tool. Available tools: {names}"
    )


def _stringify(result: CallToolResult) -> str:
    """Flatten the tool's content blocks into a single string for display."""
    parts: list[str] = []
    for block in result.content or []:
        if isinstance(block, TextContent):
            parts.append(block.text)
        else:
            parts.append(repr(block))
    return "\n".join(parts).strip() or "(empty response)"


def _resolve_command() -> str:
    """Find the mcp-resend-email binary, preferring Homebrew's Node install.

    On macOS systems with both an old /usr/local/bin/node and Homebrew's
    /opt/homebrew/bin/node, PATH-based resolution can pick the older one
    (which fails the mcp-resend-email engine check). We prefer the Homebrew
    install when present.
    """
    override = os.environ.get("MCP_RESEND_EMAIL_CMD")
    if override:
        return override
    homebrew = "/opt/homebrew/bin/mcp-resend-email"
    if os.path.exists(homebrew):
        return homebrew
    found = shutil.which("mcp-resend-email")
    if not found:
        raise RuntimeError(
            "mcp-resend-email not found. Install with "
            "`npm install -g mcp-resend-email` (using Node >= 20.18.1)."
        )
    return found


def _resolve_env() -> dict[str, str]:
    """Build a child env that prefers Homebrew node over /usr/local/bin."""
    env = os.environ.copy()
    homebrew_bin = "/opt/homebrew/bin"
    if os.path.isdir(homebrew_bin):
        path = env.get("PATH", "")
        if homebrew_bin not in path.split(os.pathsep):
            env["PATH"] = homebrew_bin + os.pathsep + path
    return env


def email_mcp_configured() -> bool:
    """Return whether the Resend MCP runtime can be used in this process."""
    if not os.environ.get("RESEND_API_KEY"):
        return False
    if not os.environ.get("RESEND_FROM_EMAIL"):
        return False
    try:
        _resolve_command()
    except RuntimeError:
        return False
    return True


async def send_email_via_mcp(*, to: str, subject: str, text: str) -> str:
    """Send a single email through the mcp-resend-email MCP server.

    Spawns the npm server fresh, calls the send-email tool, then exits.
    Returns the tool's textual response. Raises RuntimeError on tool error.
    """
    api_key = _require_env("RESEND_API_KEY")
    sender = _require_env("RESEND_FROM_EMAIL")

    params = StdioServerParameters(
        command=_resolve_command(),
        args=[f"--api-key={api_key}"],
        env=_resolve_env(),
    )

    payload: dict[str, Any] = {
        "from": sender,
        "to": to,
        "subject": subject,
        "text": text,
    }

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_name = await _find_send_tool(session)
            result = await session.call_tool(tool_name, payload)
            output = _stringify(result)
            is_error = result.isError or output.lower().startswith("failed to send")

    if is_error:
        raise RuntimeError(f"MCP send-email failed: {output}")
    return output
