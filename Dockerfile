FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Базовые утилиты
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Установка uv (менеджер пакетов)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.profile
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Ставим зависимости в слой (кэшируемо)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    && echo 'export PATH="/app/.venv/bin:$PATH"' >> /root/.profile
ENV PATH="/app/.venv/bin:$PATH"

# Копируем исходники
COPY backend ./backend

# Докпорт для дев-сервера
EXPOSE 8000

# Никакого entrypoint — команды задаём в docker-compose
CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000"]
