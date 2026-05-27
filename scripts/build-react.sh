#!/usr/bin/env bash
# 构建前端到 frontend/dist（由 FastAPI :8101 托管，与 API 同源，无需代理）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

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

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请在 WSL 安装 Node.js" >&2
  exit 1
fi

_ensure_node_modules() {
  if [ ! -d node_modules ]; then
    echo "=== 安装前端依赖 ==="
    if [ -f package-lock.json ]; then npm ci; else npm install; fi
  fi
}

if [ "$REBUILD" = 1 ]; then
  echo "=== 强制重建前端 ==="
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
  npm run build
elif [ -f dist/index.html ]; then
  echo "使用已有 frontend/dist（强制重建请加 --rebuild）"
else
  echo "=== 构建前端 ==="
  _ensure_node_modules
  npm run build
fi

echo "完成: frontend/dist → http://127.0.0.1:8101"
