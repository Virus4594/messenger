#!/bin/bash
set -e

echo "Running database migrations..."
flask db upgrade || (flask db init && flask db migrate -m "initial" && flask db upgrade)

echo "Starting Gunicorn..."
exec gunicorn app:app --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT