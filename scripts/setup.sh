#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found. Install Node.js and npm before running setup." >&2
  exit 1
fi

bash "$project_root/backend/scripts/setup.sh"
cd "$project_root/frontend"
npm ci --cache .npm-cache --no-audit --no-fund

echo "Ready. Run backend/scripts/run.sh and scripts/frontend.sh in two terminals."

