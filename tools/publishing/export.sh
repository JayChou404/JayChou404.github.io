#!/usr/bin/env bash
set -euo pipefail

python3 tools/publishing/publish.py export "$@"
