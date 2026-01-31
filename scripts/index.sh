#!/usr/bin/env bash
# Wrapper to run reindex.py within the virtual environment

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Run the python script
python3 "$PROJECT_ROOT/storage/reindex.py"
