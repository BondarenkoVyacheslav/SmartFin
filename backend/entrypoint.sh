#!/usr/bin/env sh
set -eu

ROLE="${ROLE:-backend}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-0}"
WAIT_FOR_QDRANT="${WAIT_FOR_QDRANT:-1}"
QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

echo "Waiting for database..."
python - <<'PY'
import os, time
import psycopg

url = os.environ.get('DATABASE_URL')
assert url, 'DATABASE_URL not set'

url = url.replace('postgresql+psycopg://', 'postgresql://')

for i in range(60):
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Database not reachable')
print('Database is up')
PY

if [ "$WAIT_FOR_QDRANT" = "1" ]; then
  if command -v curl >/dev/null 2>&1; then
    echo "Waiting for Qdrant at http://${QDRANT_HOST}:${QDRANT_PORT} ..."
    i=0
    until curl -fsS "http://${QDRANT_HOST}:${QDRANT_PORT}/collections" >/dev/null 2>&1; do
      i=$((i+1))
      [ "$i" -ge 60 ] && echo "Qdrant not reachable" && exit 1
      sleep 1
    done
    echo "Qdrant is up"
  fi
fi

if [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "Running Django migrations..."
  python backend/manage.py migrate --noinput
fi

case "$ROLE" in
  backend)
    echo "Starting Django development server..."
    exec python backend/manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    echo "Starting Celery worker..."
    exec python -m celery -A config worker -l info
    ;;
  beat)
    echo "Starting Celery beat..."
    exec python -m celery -A config beat -l info -S django
    ;;
  *)
    echo "Unknown ROLE=$ROLE; defaulting to backend"
    exec python backend/manage.py runserver 0.0.0.0:8000
    ;;
esac
