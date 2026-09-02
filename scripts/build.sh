#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf build function.zip
mkdir build

uv pip install httpx --target build --python-platform x86_64-manylinux2014

cp -r src/yt_gcc build/

find build -name "__pycache__" -type d -exec rm -rf {} +

cd build && zip -rq ../function.zip . && cd ..

echo "built function.zip"