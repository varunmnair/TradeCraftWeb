#!/bin/bash
cd "$(dirname "$0")/.."
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./tools/setup.sh first."
    exit 1
fi

source venv/bin/activate
python menu_cli.py
