#!/usr/bin/env bash
# 仅后端：FastAPI :8101（默认后台 detach，供 start-dev / start-prod 或直接调用）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FOREGROUND=0
for arg in "$@"; do
  case "$arg" in
    --foreground) FOREGROUND=1 ;;
  esac
done

mkdir -p .local
LOG=".local/uvicorn.log"
PID_FILE=".local/uvicorn.pid"
CRASH_LOG=".local/crash-latest.log"

_write_crash_log() {
  local c="${1:-1}"
  {
    echo "=== $(date -Is 2>/dev/null || date) exit=$c ==="
    if [ "$c" = 137 ] || [ "$c" = 143 ]; then
      echo "hint: $c 多为 OOM/SIGKILL 或终端关闭；WSL 可试: dmesg | tail -20 | grep -i kill"
    fi
    echo "--- tail uvicorn.log ---"
    tail -n 80 "$LOG" 2>/dev/null || echo "(无日志)"
    if command -v nvidia-smi >/dev/null 2>&1; then
      echo "--- nvidia-smi ---"
      nvidia-smi || true
    fi
  } >>"$CRASH_LOG"
}

_on_exit() {
  local ec=$?
  if [ "$ec" -ne 0 ] && [ "$ec" -ne 130 ]; then
    _write_crash_log "$ec"
    echo "异常退出 (code=$ec)，详情: $CRASH_LOG" >&2
  fi
}

_run_uvicorn() {
  # shellcheck source=env.sh
  . "$ROOT/scripts/env.sh"
  load_repo_env "$ROOT"
  activate_venv
  exec python -m fastapi_service.server
}

_start_foreground() {
  trap _on_exit EXIT
  echo "日志: $LOG（异常退出见 $CRASH_LOG）" >&2
  set -o pipefail
  _run_uvicorn 2>&1 | tee -a "$LOG"
  exit "${PIPESTATUS[0]}"
}

_wait_or_fail() {
  local pid=$1
  local i
  for i in $(seq 1 180); do
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
      _write_crash_log 1
      echo "FastAPI 启动失败（PID $pid 已退出）" >&2
      echo "  日志: $LOG" >&2
      echo "  诊断: $CRASH_LOG" >&2
      rm -f "$PID_FILE"
      return 1
    fi
    if grep -qE "vLLM 预加载失败|预加载异常" "$LOG" 2>/dev/null; then
      _write_crash_log 1
      echo "vLLM 预加载失败，见: $LOG" >&2
      rm -f "$PID_FILE"
      return 1
    fi
    if grep -q "Application startup complete" "$LOG" 2>/dev/null; then
      return 0
    fi
    if grep -qE "Traceback \(most recent|ModuleNotFoundError|Address already in use" "$LOG" 2>/dev/null; then
      sleep 1
      if ! kill -0 "$pid" 2>/dev/null; then
        _write_crash_log 1
        echo "FastAPI 启动失败（见日志中的 Traceback）" >&2
        echo "  日志: $LOG" >&2
        echo "  诊断: $CRASH_LOG" >&2
        rm -f "$PID_FILE"
        return 1
      fi
    fi
  done
  if kill -0 "$pid" 2>/dev/null; then
    if grep -q "vLLM 预加载完成" "$LOG" 2>/dev/null; then
      return 0
    fi
    echo "进程存活但未在日志中看到「vLLM 预加载完成」，请: tail -f $LOG"
    return 1
  fi
  _write_crash_log 1
  return 1
}

if [ "$FOREGROUND" = 1 ]; then
  _start_foreground
fi

echo "=== 检测 PostgreSQL ==="
bash "$ROOT/scripts/check-pg.sh"

if command -v fuser >/dev/null 2>&1; then
  fuser -k 8101/tcp 2>/dev/null || true
  sleep 1
fi

if [ -f frontend/dist/index.html ]; then
  echo "=== 启动 FastAPI http://127.0.0.1:8101（后台 detach，含 UI） ==="
else
  echo "=== 启动 FastAPI http://127.0.0.1:8101（后台 detach，仅 API） ==="
  echo "  提示: 无 frontend/dist，页面需先 ./scripts/build-react.sh"
fi
echo "  /docs  http://127.0.0.1:8101/docs"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "服务已在运行 PID $old_pid" >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

: >"$LOG"
nohup bash "$ROOT/scripts/run-fastapi.sh" --foreground >>"$LOG" 2>&1 &
uv_pid=$!
echo "$uv_pid" >"$PID_FILE"
disown 2>/dev/null || true

if ! _wait_or_fail "$uv_pid"; then
  exit 1
fi

echo "后台已启动 PID $uv_pid"
echo "  日志: $LOG"
echo "  停止: kill \$(cat $PID_FILE)"
echo "  模型加载: tail -f $LOG"
