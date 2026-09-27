#!/usr/bin/env bash
# Start the Django API (port 8000) and the React dev server (port 5173) together.
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x backend/.venv/bin/python ]; then
  echo "Setting up the Python environment…"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend packages…"
  npm --prefix frontend install
fi
backend/.venv/bin/python backend/manage.py migrate --noinput >/dev/null

trap 'kill 0' EXIT
backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 &
npm --prefix frontend run dev -- --open &
wait
