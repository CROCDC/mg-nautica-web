#!/usr/bin/env bash
# Local helper: rebuild containers, start the stack, tail logs.
set -euo pipefail

docker compose down
docker compose build
docker compose up -d
docker compose logs -f web
