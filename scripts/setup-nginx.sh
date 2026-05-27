#!/usr/bin/env bash
# WSL：apt 安装 nginx 并启用仓库站点配置
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_PORT="${NGINX_PORT:-80}"
SITE_NAME="my-vllm"
AVAIL="/etc/nginx/sites-available/${SITE_NAME}"
ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"
SRC="$ROOT/nginx/my-vllm.conf"

if [ ! -f "$SRC" ]; then
  echo "缺少 $SRC" >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "=== 安装 nginx（apt）==="
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
fi

echo "=== 安装站点配置 ==="
_nginx_ok() {
  curl -sf --max-time 2 "http://127.0.0.1:${NGINX_PORT:-80}/health" >/dev/null 2>&1
}

if sudo -n true 2>/dev/null; then
  SUDO=(sudo -n)
elif _nginx_ok && cmp -s "$SRC" "$AVAIL" 2>/dev/null; then
  echo "Nginx 已在运行且配置未变，跳过 sudo（更新配置请在终端执行 sudo $0）"
  exit 0
else
  echo "需要 sudo 配置 Nginx（建议配置免密 sudo 或在终端手动执行本脚本）" >&2
  SUDO=(sudo)
fi

"${SUDO[@]}" cp "$SRC" "$AVAIL"
"${SUDO[@]}" ln -sf "$AVAIL" "$ENABLED"
if [ -f /etc/nginx/sites-enabled/default ]; then
  "${SUDO[@]}" rm -f /etc/nginx/sites-enabled/default
fi

"${SUDO[@]}" nginx -t
"${SUDO[@]}" systemctl enable nginx
"${SUDO[@]}" systemctl reload nginx

echo "Nginx 已配置: $ENABLED"
