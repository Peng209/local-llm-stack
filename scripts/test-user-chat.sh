#!/usr/bin/env bash
# 使用指定账号测试登录与聊天（默认直连 FastAPI :8101）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
load_repo_env "$ROOT"
activate_venv 2>/dev/null || true

if [ "${TEST_VIA_NGINX:-0}" = "1" ]; then
  NGINX_PORT="$(python3 -c "from fastapi_service import config; print(config.NGINX_HTTP_PORT)" 2>/dev/null || echo 80)"
  BASE="http://127.0.0.1:${NGINX_PORT}"
else
  BASE="http://127.0.0.1:8101"
fi
EMAIL="${TEST_EMAIL:-2091667818@qq.com}"
PASS="${TEST_PASS:-123456}"

echo "=== POST /api/auth/login ($EMAIL) ==="
if ! TOKEN=$(curl -sf -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"); then
  echo "登录失败，尝试注册…"
  TOKEN=$(curl -sf -X POST "$BASE/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
fi
echo "token ok (${#TOKEN} chars)"

echo ""
echo "=== POST /api/chat 非流式 ==="
CHAT_OUT="$ROOT/.local/test-chat-response.txt"
HTTP_CODE=$(curl -s -o "$CHAT_OUT" -w "%{http_code}" --max-time 900 \
  -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"你好，请用一句话自我介绍","stream":false,"max_tokens":128}')
echo "HTTP $HTTP_CODE"
if [ "$HTTP_CODE" != "200" ]; then
  head -c 2000 "$CHAT_OUT" >&2
  exit 1
fi
python3 -m json.tool <"$CHAT_OUT"

echo ""
echo "用户聊天测试通过。"
