#!/usr/bin/env bash
# 启动前检测 PostgreSQL；未运行时尝试 docker start pg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=env.sh
. "$ROOT/scripts/env.sh"
load_repo_env "$ROOT"

PG_HOST=127.0.0.1
PG_PORT=5432
if [[ "${DATABASE_URL:-}" =~ @([^:/]+)(:([0-9]+))?/ ]]; then
  PG_HOST="${BASH_REMATCH[1]}"
  PG_PORT="${BASH_REMATCH[3]:-5432}"
fi

try_pg() { nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null; }

start_pg() {
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "docker start pg" >/dev/null 2>&1 || true
  else
    docker start pg >/dev/null 2>&1 || true
  fi
}

try_pg || { echo "PostgreSQL 未响应，尝试 docker start pg …" >&2; start_pg; }

for _ in 1 2 3 4 5; do
  try_pg && { echo "=== PostgreSQL 已就绪 ==="; exit 0; }
  sleep 2
done

echo "错误: 无法连接 PostgreSQL ($PG_HOST:$PG_PORT)。请先执行: docker start pg" >&2
exit 1
