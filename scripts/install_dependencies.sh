#!/usr/bin/env bash
# WSL 一次性安装：apt + ~/.virtualenvs/my-vllm + 前端 + Nginx 站点
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"

echo "=== apt ==="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx curl nodejs npm ca-certificates python3-venv

if ! command -v ngrok >/dev/null 2>&1; then
  curl -fsSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
    | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
  echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
    | sudo tee /etc/apt/sources.list.d/ngrok.list >/dev/null
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ngrok || true
fi

echo "=== venv: $VENV ==="
if [ ! -d "$VENV" ]; then
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
fi
activate_venv
pip install -U pip wheel

if command -v uv >/dev/null 2>&1; then
  uv pip install vllm --torch-backend=auto
else
  pip install vllm
fi
pip install -r "$ROOT/requirements.txt"

cd "$ROOT"
if python -c "from fastapi_service import config; m=config.VLLM_MODEL.lower(); exit(0 if 'qwen2-vl' in m or 'qwen2_vl' in m else 1)"; then
  pip install --no-deps 'qwen-vl-utils==0.0.14'
fi

echo "=== npm ==="
cd "$ROOT/frontend"
if [ -f package-lock.json ]; then npm ci; else npm install; fi

echo "=== nginx ==="
bash "$ROOT/scripts/setup-nginx.sh"
echo "完成。venv=$VENV  下一步: cp .env.example .env && ./scripts/run.sh"
