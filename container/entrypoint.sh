#!/bin/bash
set -e

# Refactored Container Entrypoint - Minimal orchestrator
# Delegates to specialized modules for maintainability

CONTAINER_LIB_DIR="${CONTAINER_LIB_DIR:-/usr/local/container/lib}"
CONTAINER_CONFIG_DIR="${CONTAINER_CONFIG_DIR:-/usr/local/container/config}"

# Core environment setup
BASE_BRANCH="${BASE_BRANCH:-main}"
BRANCH_NAME="${BRANCH_NAME:-feature/auto-fix}"
TASK_SPEC_FILE="${TASK_SPEC_FILE:-/tmp/task_spec.md}"
LANGUAGE="${LANGUAGE:-python}"
AI_PROVIDER="${AI_PROVIDER:-claude}"

echo "🚀 Starting Claude Agent Container"

# Load configuration
source "$CONTAINER_LIB_DIR/git_setup.sh"
source "$CONTAINER_LIB_DIR/auth_setup.sh" 
source "$CONTAINER_LIB_DIR/env_setup.sh"

# Setup authentication FIRST (needed for git operations)
setup_authentication "$AI_PROVIDER"

# Setup git workspace (after authentication is configured)
setup_git_workspace "$BASE_BRANCH" "$BRANCH_NAME"

# Record starting commit for diff calculation (after git is properly configured)
STARTING_COMMIT=$(git rev-parse HEAD)
export STARTING_COMMIT
echo "📊 Starting commit: ${STARTING_COMMIT:0:8}"

# # Create cost data directory for job manager integration
mkdir -p /tmp/cost_data

# # Setup language environment
setup_language_environment "$LANGUAGE"

# # Execute AI provider
echo "🤖 Executing $AI_PROVIDER provider..."
python3 "$CONTAINER_LIB_DIR/ai_executor.py" \
    --provider "$AI_PROVIDER" \
    --task-spec "$TASK_SPEC_FILE" \
    --branch "$BRANCH_NAME" \
    --base-branch "$BASE_BRANCH" \
    --language "$LANGUAGE" \
    --starting-commit "$STARTING_COMMIT"

AI_EXIT_CODE=$?

# # Generate final session summary
python3 "$CONTAINER_LIB_DIR/cost_monitor.py" --finalize --starting-commit "$STARTING_COMMIT"

echo "✅ Container execution completed (exit code: $AI_EXIT_CODE)"
exit $AI_EXIT_CODE