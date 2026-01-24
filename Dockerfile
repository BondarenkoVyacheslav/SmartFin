FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ARG APP_UID=1000
ARG APP_GID=1000

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN if ! getent group "${APP_GID}" >/dev/null; then groupadd -g "${APP_GID}" app; fi \
  && if ! id -u "${APP_UID}" >/dev/null 2>&1; then useradd -m -u "${APP_UID}" -g "${APP_GID}" app; fi \
  && mkdir -p /app \
  && chown -R "${APP_UID}:${APP_GID}" /app

USER ${APP_UID}:${APP_GID}
WORKDIR /app

COPY --chown=${APP_UID}:${APP_GID} pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=${APP_UID}:${APP_GID} backend ./backend

WORKDIR /app/backend
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
