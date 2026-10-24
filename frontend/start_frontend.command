#!/bin/zsh
set -e
cd "$(dirname "$0")"
echo "Opening Screenslavers Investigator Workspace..."
echo "Start Member 4 FastAPI backend on 127.0.0.1:8000 in another Terminal."
(sleep 2; open http://127.0.0.1:5173/) &
exec python3 -m http.server 5173 --bind 127.0.0.1
