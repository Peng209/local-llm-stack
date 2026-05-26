#!/usr/bin/env bash

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
activate_venv

echo "=== 检测 PostgreSQL ==="
bash "$ROOT/scripts/check-pg.sh"

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请在 WSL 安装 Node.js" >&2
  exit 1
fi


echo "=== 构建 React 前端 ==="
cd frontend
# 如果参数是 "rebuild"，则强制重建
if [ -n "$1" ] && [ "$1" = "--rebuild" ]; then
  echo "强制重建模式"
  # 确保依赖存在
  if [ ! -d node_modules ]; then
    if [ -f package-lock.json ]; then npm ci; else npm install; fi
  fi
  npm run build
elif [ -f dist/index.html ]; then
  echo "使用已有 frontend/dist（如需重建请传入 --rebuild 参数）"
else
  echo "未找到 dist/index.html，开始构建..."
  if [ ! -d node_modules ]; then
    if [ -f package-lock.json ]; then npm ci; else npm install; fi
  fi
  npm run build
fi
cd "$ROOT"


echo "=== 启动 FastAPI http://127.0.0.1:8101 ==="
exec python -m uvicorn fastapi_service.main:app --host 127.0.0.1 --port 8101
