FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY skills ./skills

RUN pip install --no-cache-dir .

ENV JIZHANG_HOST=0.0.0.0
ENV JIZHANG_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "jizhang_mcp.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
