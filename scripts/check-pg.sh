#!/usr/bin/env bash
# 启动前检测 PostgreSQL；未运行时尝试 docker start pg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/scripts/env.sh" ]; then
  # shellcheck source=env.sh
  . "$ROOT/scripts/env.sh"
  activate_venv 2>/dev/null || true
fi

try_pg() {
  python3 <<'PY'
import asyncio
import re
import sys

from fastapi_service import config

url = config.DATABASE_URL
m = re.match(
    r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?\s]+)",
    url,
)
if not m:
    print(f"无法解析 DATABASE_URL: {url}", file=sys.stderr)
    sys.exit(1)

user, password, host, port, db = m.groups()
port = port or "5432"


async def main() -> None:
    import asyncpg

    conn = await asyncio.wait_for(
        asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=db,
        ),
        timeout=5,
    )
    await conn.close()


asyncio.run(main())
PY
}

if try_pg 2>/dev/null; then
  echo "=== PostgreSQL 已就绪 ==="
  exit 0
fi

echo "PostgreSQL 未响应，尝试 docker start pg …" >&2
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -Command "docker start pg" >/dev/null 2>&1 || true
elif command -v docker >/dev/null 2>&1; then
  docker start pg >/dev/null 2>&1 || true
fi

for i in 1 2 3 4 5; do
  sleep 2
  if try_pg 2>/dev/null; then
    echo "=== PostgreSQL 已就绪（docker start 后） ==="
    exit 0
  fi
  echo "等待 PostgreSQL… ($i/5)" >&2
done

echo "错误: 无法连接 PostgreSQL。请先执行: docker start pg" >&2
echo "并确认 .env 中 DATABASE_URL 与容器密码一致。" >&2
exit 1
