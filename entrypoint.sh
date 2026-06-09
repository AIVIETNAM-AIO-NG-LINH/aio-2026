#!/bin/sh
set -e

echo ">> Waiting for database at ${DB_HOST:-db}:${DB_PORT:-3306} ..."
python <<'PYEOF'
import os, socket, time

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "3306"))

for attempt in range(1, 61):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("   database is reachable")
            break
    except OSError:
        print(f"   not ready yet (attempt {attempt}/60)")
        time.sleep(2)
else:
    raise SystemExit("ERROR: database not reachable after 120s")
PYEOF

echo ">> Applying database migrations ..."
python manage.py migrate --noinput

echo ">> Starting: $*"
exec "$@"
