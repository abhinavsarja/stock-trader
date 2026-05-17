# Chainlit stock-trader — AWS App Runner / ECS compatible
# Step 1 (verify locally):
#   docker build -t stock-trader:local .
#   docker run --rm -p 8080:8080 --env-file .env stock-trader:local
#   open http://localhost:8080

FROM node:20-bookworm-slim AS resend-mcp

RUN npm install -g mcp-resend-email

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv

# Runtime dependency for main/src/trader/email_sender.py.
# The app talks to this MCP server over stdio when a user requests email delivery.
COPY --from=resend-mcp /usr/local/bin/node /usr/local/bin/node
COPY --from=resend-mcp /usr/local/bin/npm /usr/local/bin/npm
COPY --from=resend-mcp /usr/local/bin/npx /usr/local/bin/npx
COPY --from=resend-mcp /usr/local/bin/mcp-resend-email /usr/local/bin/mcp-resend-email
COPY --from=resend-mcp /usr/local/lib/node_modules /usr/local/lib/node_modules

WORKDIR /app

COPY pyproject.toml uv.lock README.md app.py chainlit.md ./
COPY main ./main
COPY .chainlit ./.chainlit

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# AWS / ALB commonly forward to 8080; keep PORT aligned with ECS target port.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec chainlit run app.py --host 0.0.0.0 --port ${PORT:-8080}"]
