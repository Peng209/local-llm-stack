#!/usr/bin/env bash
# FastAPI :8101（默认后台 detach）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG=".local/uvicorn.log"
PID_FILE=".local/uvicorn.pid"

_health_ok() {
  curl -sf --max-time 3 http://127.0.0.1:8101/health >/dev/null 2>&1
}

if [ "${1:-}" = --foreground ]; then
  # shellcheck source=env.sh
  . "$ROOT/scripts/env.sh"
  load_repo_env "$ROOT"
  activate_venv
  exec python -m fastapi_service.server
fi

mkdir -p .local
bash "$ROOT/scripts/check-pg.sh"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null && _health_ok; then
    echo "FastAPI 已在运行 PID $old_pid"
    exit 0
  fi
  kill "$old_pid" 2>/dev/null || true
  rm -f "$PID_FILE"
fi

command -v fuser >/dev/null 2>&1 && fuser -k 8101/tcp 2>/dev/null || true
sleep 1

echo "=== 启动 FastAPI http://127.0.0.1:8101 ==="
: >"$LOG"
nohup bash "$0" --foreground >>"$LOG" 2>&1 &
uv_pid=$!
echo "$uv_pid" >"$PID_FILE"

for _ in $(seq 1 180); do
  _health_ok && { echo "后台已启动 PID $uv_pid · 日志 $LOG"; exit 0; }
  kill -0 "$uv_pid" 2>/dev/null || break
  sleep 2
done

echo "FastAPI 启动失败，见 $LOG" >&2
rm -f "$PID_FILE"
exit 1
