#!/bin/bash

# Check if VERSION environment is set
if [ -z "$VERSION" ]; then
  echo "ERROR: VERSION environment variable is not set"
  exit 1
fi

# If not triggered for local build, check for TWINE_PASSWORD
if [ -z "$LOCAL_BUILD" ]; then
  # Check if TWINE_PASSWORD is set
  if [ -z "$TWINE_PASSWORD" ]; then
    echo "ERROR: TWINE_PASSWORD environment variable is not set"
    exit 1
  fi
fi

rm -rf dist
rm -rf build
cat pyproject.toml | sed -i "s/version = \"[^\"]*\"/version = \"$VERSION\"/" pyproject.toml

# Build x86_64 wheel
rm -rf ./mariadb_binlog_indexer/lib || true
mkdir -p ./mariadb_binlog_indexer/lib
cd ./indexer
CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -o ../mariadb_binlog_indexer/lib/indexer
cd ../
chmod +x ./mariadb_binlog_indexer/lib/indexer
pip wheel . --no-deps --wheel-dir dist --config-settings="--build-option=--plat-name=manylinux2014_x86_64"

# Build arm64 wheel
rm -rf ./mariadb_binlog_indexer/lib || true
mkdir -p ./mariadb_binlog_indexer/lib
cd ./indexer
CGO_ENABLED=1 GOOS=linux GOARCH=arm64 CC=aarch64-linux-gnu-gcc go build -o ../mariadb_binlog_indexer/lib/indexer
cd ../
chmod +x ./mariadb_binlog_indexer/lib/indexer
pip wheel . --no-deps --wheel-dir dist --config-settings="--build-option=--plat-name=manylinux2014_aarch64"

if [ -z "$LOCAL_BUILD" ]; then
  pip install build twine
  twine upload dist/* --non-interactive
fi
