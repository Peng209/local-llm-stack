#!/usr/bin/env bash
set -euo pipefail

SITE="/etc/nginx/sites-enabled/my-vllm"
if [ -L "$SITE" ] || [ -f "$SITE" ]; then
  sudo rm -f "$SITE"
  sudo nginx -t
  sudo systemctl reload nginx
  echo "Nginx 站点 my-vllm 已禁用。"
fi
