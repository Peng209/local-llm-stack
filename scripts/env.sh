# shellcheck shell=bash
VENV="${HOME}/.virtualenvs/my-vllm"

activate_venv() {
  if [ ! -f "${VENV}/bin/activate" ]; then
    echo "请先运行: ./scripts/install_dependencies.sh" >&2
    exit 1
  fi
  # shellcheck source=/dev/null
  . "${VENV}/bin/activate"
}

load_repo_env() {
  local root="${1:-}"
  if [ -z "$root" ] && [ -n "${BASH_SOURCE[0]:-}" ]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  fi
  if [ -f "${root}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${root}/.env"
    set +a
  fi
}
