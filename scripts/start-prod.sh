#!/usr/bin/env bash
# 正式：run-nginx-and-ngrok.sh → build-react.sh → run-fastapi.sh → 监控日志
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    *)
      echo "未知参数: $arg（仅支持 --rebuild）" >&2
      exit 1
      ;;
  esac
done

BUILD_ARGS=()
if [ "$REBUILD" = 1 ]; then
  BUILD_ARGS+=(--rebuild)
fi

bash "$ROOT/scripts/run-nginx-and-ngrok.sh"
bash "$ROOT/scripts/build-react.sh" "${BUILD_ARGS[@]}"
bash "$ROOT/scripts/run-fastapi.sh"

LOG=".local/uvicorn.log"
PID="$(cat .local/uvicorn.pid)"

echo ""
echo "=== 监控中 · PID $PID · Ctrl+C 仅退出监控（服务继续后台运行）==="
tail -f "$LOG" &
tail_pid=$!
trap 'kill "$tail_pid" 2>/dev/null; exit 0' INT

while kill -0 "$PID" 2>/dev/null; do sleep 3; done
kill "$tail_pid" 2>/dev/null
echo ""
echo "FastAPI 已退出 (PID $PID)，见 $LOG" >&2
exit 1
