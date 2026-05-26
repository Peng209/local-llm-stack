#!/usr/bin/env bash
set -euo pipefail
BASE="http://127.0.0.1:${NGINX_HTTP_PORT:-80}"
EMAIL="vl-$RANDOM@example.com"
TOKEN=$(curl -sf -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"testpass123\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "chat text..."
curl -sf --max-time 600 -X POST "$BASE/api/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"用一句话说你好","stream":false,"max_tokens":32}' \
  | python3 -m json.tool | head -15
echo "chat image..."
TINY="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
curl -sf --max-time 600 -X POST "$BASE/api/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"这是什么颜色\",\"image_urls\":[\"$TINY\"],\"stream\":false,\"max_tokens\":64}" \
  | python3 -m json.tool | head -15
echo "ok"
