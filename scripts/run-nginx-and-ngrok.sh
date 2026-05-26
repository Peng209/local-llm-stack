#!/usr/bin/env bash
# 启动 Nginx（:80 → FastAPI :8101）与 ngrok 隧道（需 .env 中 NGROK_TOKEN）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/.local"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
activate_venv 2>/dev/null || true

NGINX_PORT="$(python3 -c "from fastapi_service import config; print(config.NGINX_HTTP_PORT)" 2>/dev/null || echo 80)"
NGROK_LOG="$ROOT/.local/ngrok.log"

echo "=== 配置并启动 Nginx ==="
chmod +x "$ROOT/scripts/setup-nginx.sh"
bash "$ROOT/scripts/setup-nginx.sh"
sudo systemctl start nginx
sudo systemctl --no-pager status nginx | head -5 || true
echo "Nginx: http://127.0.0.1:${NGINX_PORT} → 127.0.0.1:8101"
echo "停止站点: ./scripts/stop-nginx.sh"

if [ -z "${NGROK_TOKEN:-}" ]; then
  echo ""
  echo "未设置 NGROK_TOKEN（.env），仅 Nginx 已启动。" >&2
  exit 0
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "错误: 未找到 ngrok，请先运行 ./scripts/install_dependencies.sh" >&2
  exit 1
fi

echo ""
echo "=== 启动 ngrok ==="
ngrok config add-authtoken "$NGROK_TOKEN"

if pgrep -f "ngrok http ${NGINX_PORT}" >/dev/null 2>&1 || pgrep -f "ngrok http 80" >/dev/null 2>&1; then
  echo "ngrok 已在运行，跳过重复启动。"
  exit 0
fi

nohup ngrok http "$NGINX_PORT" >"$NGROK_LOG" 2>&1 &
sleep 2
if ! pgrep -f "ngrok http" >/dev/null 2>&1; then
  echo "ngrok 启动失败，查看日志: $NGROK_LOG" >&2
  tail -20 "$NGROK_LOG" >&2 || true
  exit 1
fi

echo "ngrok 已后台启动（http ${NGINX_PORT}）"
echo "  日志: $NGROK_LOG"
echo "  控制台: http://127.0.0.1:4040 （若未改默认）"
echo "结束 ngrok: pkill -f 'ngrok http'"
