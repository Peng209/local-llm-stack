#!/usr/bin/env bash
# 冒烟测试（经 Nginx :80）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
activate_venv 2>/dev/null || true

NGINX_PORT="$(python3 -c "from fastapi_service import config; print(config.NGINX_HTTP_PORT)" 2>/dev/null || echo 80)"
BASE="http://127.0.0.1:${NGINX_PORT}"
TEST_EMAIL="stack-test-$RANDOM@example.com"
TEST_PASS="testpass123"

echo "=== 1. /health ==="
curl -sf "$BASE/health" | python3 -m json.tool

echo ""
echo "=== 2. GET / (React) ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
echo "HTTP $code"

echo ""
echo "=== 3. GET /api/config ==="
curl -sf "$BASE/api/config" | python3 -m json.tool

echo ""
echo "=== 4. POST /api/auth/register ==="
TOKEN=$(curl -sf -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "token ok (${#TOKEN} chars)"

echo ""
echo "=== 5. POST /api/chat 非流式 ==="
curl -sf --max-time 600 -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"用一句话说你好","stream":false,"max_tokens":64}' \
  | python3 -m json.tool

echo ""
echo "=== 6. POST /api/chat 流式 SSE ==="
STREAM_OUT=$(curl -sf --max-time 600 -N -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"数到3","stream":true,"max_tokens":32}')
if ! echo "$STREAM_OUT" | grep -q '^data:'; then
  echo "流式响应未返回 SSE data: 行" >&2
  echo "$STREAM_OUT" | head -5 >&2
  exit 1
fi
echo "收到 $(echo "$STREAM_OUT" | grep -c '^data:' || true) 个 SSE 块"

echo ""
echo "=== 7. GET /api/conversations ==="
CONV_LIST=$(curl -sf "$BASE/api/conversations" \
  -H "Authorization: Bearer $TOKEN")
echo "$CONV_LIST" | python3 -m json.tool

echo ""
echo "=== 8. POST /api/conversations + DELETE ==="
CONV_ID=$(curl -sf -X POST "$BASE/api/conversations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"删除测试"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
code=$(curl -s -o /tmp/del-test.txt -w "%{http_code}" -X DELETE \
  "$BASE/api/conversations/$CONV_ID" \
  -H "Authorization: Bearer $TOKEN")
if [ "$code" != "204" ]; then
  echo "DELETE 失败 HTTP $code" >&2
  cat /tmp/del-test.txt >&2
  exit 1
fi
echo "DELETE 对话 HTTP 204"

echo ""
echo "=== 9. POST /api/chat 仅图片（校验多模态请求体） ==="
# 1x1 PNG，不等待模型完整推理；只验证 API 接受 image_urls
TINY_PNG="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
code=$(curl -s -o /tmp/img-chat.txt -w "%{http_code}" --max-time 600 \
  -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"message\":\"描述图片\",\"image_urls\":[\"$TINY_PNG\"],\"stream\":false,\"max_tokens\":16}")
if [ "$code" != "200" ] && [ "$code" != "503" ]; then
  echo "带图片 chat 失败 HTTP $code" >&2
  head -c 500 /tmp/img-chat.txt >&2
  exit 1
fi
echo "带图片 chat HTTP $code"

echo ""
echo "全部通过。"
