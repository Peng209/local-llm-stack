#!/usr/bin/env bash
# WSL：apt 安装 nginx 并启用仓库站点配置
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
sudo cp "$SRC" "$AVAIL"
sudo ln -sf "$AVAIL" "$ENABLED"
if [ -f /etc/nginx/sites-enabled/default ]; then
  sudo rm -f /etc/nginx/sites-enabled/default
fi

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

echo "Nginx 已配置: $ENABLED"
