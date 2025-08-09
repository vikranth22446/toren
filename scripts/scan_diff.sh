#!/bin/bash
set -e

echo "🔍 Git Diff Security Scan"
echo "========================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

# Parse arguments
CACHED=""
DIFF_TARGET="HEAD"

while [[ $# -gt 0 ]]; do
    case $1 in
        --cached)
            CACHED="--cached"
            DIFF_TARGET=""
            echo "Scanning staged changes"
            ;;
        *)
            DIFF_TARGET="$1"
            echo "Scanning changes against: $DIFF_TARGET"
            ;;
    esac
    shift
done

# Create temporary file for diff
DIFF_FILE=$(mktemp)
if [ -n "$CACHED" ]; then
    git diff --cached --name-only > "$DIFF_FILE"
else
    git diff --name-only "$DIFF_TARGET" > "$DIFF_FILE"
fi

if [ ! -s "$DIFF_FILE" ]; then
    echo "ℹ️  No changes detected"
    rm "$DIFF_FILE"
    exit 0
fi

echo "📄 Files changed:"
cat "$DIFF_FILE" | sed 's/^/  /'

# Install bandit if not present
if ! command -v bandit &> /dev/null; then
    echo "Installing bandit..."
    pip install bandit
fi

echo
echo "🔒 Running security scan on changed Python files..."

# Filter for Python files
PYTHON_FILES=$(cat "$DIFF_FILE" | grep '\.py$' || true)

if [ -z "$PYTHON_FILES" ]; then
    echo "ℹ️  No Python files changed"
    rm "$DIFF_FILE"
    exit 0
fi

echo "Python files to scan:"
echo "$PYTHON_FILES" | sed 's/^/  /'

# Create temporary file list for bandit
TEMP_PY_LIST=$(mktemp)
echo "$PYTHON_FILES" > "$TEMP_PY_LIST"

# Run bandit on changed files only
echo
echo "🛡️  Security scan results:"
echo "=========================="

# Run bandit with optimized settings for speed
BANDIT_RESULT=0
echo "Files being scanned:"
cat "$TEMP_PY_LIST" | sed 's/^/  /'

# Use faster bandit options:
# -ll: only high/medium severity (skip low severity for speed)  
# -f screen: faster than JSON output
# --skip-path: skip common non-security paths
# --ini .bandit: use configuration file
echo
START_TIME=$(date +%s)
bandit -ll -f screen --ini .bandit \
    --skip B101 \
    $(tr '\n' ' ' < "$TEMP_PY_LIST") || BANDIT_RESULT=$?
END_TIME=$(date +%s)
SCAN_TIME=$((END_TIME - START_TIME))

echo
echo "⏱️  Scan completed in ${SCAN_TIME} seconds"

# Cleanup
rm "$DIFF_FILE" "$TEMP_PY_LIST"

echo
if [ $BANDIT_RESULT -eq 0 ]; then
    echo "✅ No security issues found in changed files"
else
    echo "⚠️  Security issues detected in changed files"
    echo "Please review and fix issues before committing"
    exit 1
fi