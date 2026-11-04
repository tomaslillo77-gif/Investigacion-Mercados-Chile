#!/usr/bin/env bash
# Arranca PostgreSQL (si hace falta) y el dashboard, accesible por IP en la red interna.
# Uso: scripts/run.sh            (usa el Excel de config/excel.yaml)
#      WM_EXCEL="data/Engine WM Dummy.xlsx" scripts/run.sh   (dummy original, con columnas faltantes)
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
PORT="${PORT:-8501}"

if command -v pg_isready >/dev/null 2>&1; then
  if ! pg_isready -q; then
    echo "Iniciando PostgreSQL…"
    brew services start postgresql@16 >/dev/null 2>&1 || true
    sleep 3
  fi
  pg_isready -q || echo "AVISO: PostgreSQL no responde; comentarios y feedback quedarán deshabilitados."
else
  echo "AVISO: PostgreSQL no está instalado; comentarios y feedback quedarán deshabilitados."
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: el puerto ${PORT} ya está en uso (¿ya hay un dashboard corriendo?)."
  echo "Ábrelo en http://localhost:${PORT} o detenlo con:  pkill -f 'streamlit run'"
  exit 1
fi

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
echo "Dashboard en http://${IP}:${PORT}  (desde esta máquina: http://localhost:${PORT})"
# Abre el navegador en esta máquina (desactívalo con NO_OPEN=1)
if [ -z "${NO_OPEN:-}" ]; then
  ( sleep 4; open "http://localhost:${PORT}" ) >/dev/null 2>&1 &
fi
# caffeinate -dis evita la suspensión mientras el dashboard corra (no evita bloqueo de pantalla ni cierre de sesión)
exec caffeinate -dis ./venv/bin/streamlit run app_v4_final.py \
  --server.address 0.0.0.0 --server.port "${PORT}" --server.headless true
