# Chainlit stock-trader — AWS App Runner / ECS compatible
# Step 1 (verify locally):
#   docker build -t stock-trader:local .
#   docker run --rm -p 8080:8080 --env-file .env stock-trader:local
#   open http://localhost:8080

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv

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
