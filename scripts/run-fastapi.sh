#!/usr/bin/env bash
# WSL 本地 dev：仅 FastAPI :8101（不经 Nginx；需已有 frontend/dist）
set -euo pipefail


ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
activate_venv

if [ ! -f frontend/dist/index.html ]; then
  echo "frontend/dist 不存在，请先 ./scripts/run.sh" >&2
  exit 1
fi

echo "=== 检测 PostgreSQL ==="
bash "$ROOT/scripts/check-pg.sh"

echo "=== 启动 FastAPI http://127.0.0.1:8101 ==="
exec python -m uvicorn fastapi_service.main:app --host 127.0.0.1 --port 8101
