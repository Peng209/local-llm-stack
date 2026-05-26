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
