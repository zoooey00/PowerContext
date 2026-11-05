#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Please run: python bootstrap.py"
  exit 1
fi
exec ./.venv/bin/python run.py
