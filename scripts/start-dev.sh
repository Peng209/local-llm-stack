#!/usr/bin/env bash
# 开发：build-react.sh 构建 dist + run-fastapi.sh 后台启动（同源 :8101）

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    *)
      echo "未知参数: $arg（仅支持 --rebuild）" >&2
      exit 1
      ;;
  esac
done

REACT_ARGS=()
if [ "$REBUILD" = 1 ]; then
  REACT_ARGS+=(--rebuild)
fi
bash "$ROOT/scripts/build-react.sh" "${REACT_ARGS[@]}"
bash "$ROOT/scripts/run-fastapi.sh"
