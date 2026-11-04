#!/usr/bin/env bash
# Respaldo diario de la base wm; conserva 14 días.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
mkdir -p backups
pg_dump wm | gzip > "backups/wm_$(date +%F).sql.gz"
find backups -name 'wm_*.sql.gz' -mtime +14 -delete
