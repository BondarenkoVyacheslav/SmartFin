#!/usr/bin/env sh
set -eu

# Ensure env file is considered only if mounted into image; settings.py loads BASE_DIR/.env
echo "Waiting for database..."
python - <<'PY'
import os, time
import psycopg
import urllib.parse

url = os.environ.get('DATABASE_URL')
assert url, 'DATABASE_URL not set'

# psycopg.connect supports postgresql:// and postgresql+psycopg://
url = url.replace('postgresql+psycopg://', 'postgresql://')

for i in range(60):
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            break
    except Exception as e:
        time.sleep(1)
else:
    raise SystemExit('Database not reachable')
print('Database is up')
PY

echo "Running Django migrations..."
python backend/manage.py migrate --noinput

echo "Starting Django development server..."
exec python backend/manage.py runserver 0.0.0.0:8000

