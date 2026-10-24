#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/frontend"
exec python3 -m http.server 5173 --bind 127.0.0.1
