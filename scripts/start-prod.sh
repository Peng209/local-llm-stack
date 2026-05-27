#!/usr/bin/env bash
# 正式：run-nginx-and-ngrok.sh → build-react.sh → run-fastapi.sh（Nginx/ngrok 不依赖后端，先起）

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

echo ""
echo "=== 健康检查 ==="
if curl -sf --max-time 5 http://127.0.0.1:8101/health; then
  echo ""
  echo "FastAPI 正常。若稍后 curl 变 000，多为 vLLM 加载 OOM，见: tail -50 .local/uvicorn.log"
else
  echo "FastAPI 无响应 (curl 000/超时)" >&2
  echo "  日志: .local/uvicorn.log" >&2
  echo "  诊断: .local/crash-latest.log（若存在）" >&2
  echo "  常见: 显存不足 → .env 设 VLLM_GPU_MEMORY_UTILIZATION=0.35 或 VLLM_PRELOAD_AT_STARTUP=false" >&2
  exit 1
fi
