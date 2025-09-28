FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Rust-based Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.profile
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy lockfiles first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a local venv
RUN uv sync --frozen --no-dev \
    && echo 'export PATH="/app/.venv/bin:$PATH"' >> /root/.profile
ENV PATH="/app/.venv/bin:$PATH"

# Copy source
COPY backend ./backend
COPY main_db_script.sql ./main_db_script.sql

# Entrypoint
COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]


