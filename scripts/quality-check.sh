#!/bin/bash
set -e

cd "$(dirname "$0")/.."

PYTHON_FILES=$(find . -name "*.py" -not -path "./build/*")
MAIN_FILES="ai_cli_interface.py toren.py cli_parser.py input_validator.py job_manager.py github_utils.py ui_utilities.py"

if [ "$1" = "--fix" ]; then
    echo "🔧 Fixing code..."
    isort $PYTHON_FILES --profile black
    autoflake --in-place --remove-all-unused-imports --remove-unused-variables $PYTHON_FILES
    black --line-length 88 $PYTHON_FILES
    echo "✅ Code fixed"
fi

echo "🐍 Syntax check..."
python3 -c "
import ast
for f in '$MAIN_FILES'.split():
    with open(f) as file: ast.parse(file.read())
"

echo "📋 Style check..."
flake8 $PYTHON_FILES --max-line-length=88 --ignore=E203,W503,E501 --count

echo "🔍 Type check..."
if [ -f "mypy.ini" ]; then
    mypy $MAIN_FILES --config-file mypy.ini
else
    mypy $MAIN_FILES --ignore-missing-imports
fi

echo "✅ All checks passed"