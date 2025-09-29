#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: manage.sh --env <dev|prod> <command> [args...]

Commands:
  up        Run docker compose up
  down      Run docker compose down
  restart   Run docker compose restart
  pull      Run docker compose pull

Any additional args after the command are forwarded to docker compose.
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

if [[ $1 != "--env" ]]; then
  echo "ERROR: first argument must be --env" >&2
  usage
  exit 1
fi

APP_ENV=${2}
shift 2

case "${APP_ENV}" in
  dev|prod) ;;
  *)
    echo "ERROR: --env must be dev or prod" >&2
    usage
    exit 1
    ;;
esac

if [[ $# -lt 1 ]]; then
  echo "ERROR: missing command" >&2
  usage
  exit 1
fi

COMMAND=$1
shift

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${SCRIPT_DIR}"

case "${APP_ENV}" in
  dev)
    COMPOSE_FILE="docker-compose.yml"
    ;;
  prod)
    COMPOSE_FILE="docker-compose-prod.yml"
    ;;
esac

compose() {
  docker compose -f "${COMPOSE_FILE}" "$@"
}

case "${COMMAND}" in
  up)
    compose up "$@"
    ;;
  down)
    compose down "$@"
    ;;
  restart)
    compose restart "$@"
    ;;
  pull)
    compose pull "$@"
    ;;
  *)
    echo "ERROR: unsupported command ${COMMAND}" >&2
    usage
    exit 1
    ;;
esac
