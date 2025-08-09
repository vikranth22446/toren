#!/bin/bash
set -e

# Container entrypoint for Claude Agent
# Handles git setup, branch creation, and Claude Code execution

BASE_BRANCH="${BASE_BRANCH:-main}"
BRANCH_NAME="${BRANCH_NAME:-feature/auto-fix}"
TASK_SPEC_FILE="${TASK_SPEC_FILE:-/tmp/task_spec.md}"
LANGUAGE="${LANGUAGE:-python}"

echo "🔄 Setting up git environment..."

# Configure git if not already configured
if [ -z "$(git config user.name)" ]; then
    git config user.name "Claude Agent"
fi
if [ -z "$(git config user.email)" ]; then
    git config user.email "claude-agent@anthropic.com"
fi

echo "📥 Fetching latest changes..."
git fetch origin

echo "🌿 Checking out base branch: $BASE_BRANCH"
git checkout "$BASE_BRANCH"

echo "📡 Pulling latest changes from $BASE_BRANCH..."
git pull origin "$BASE_BRANCH"

echo "🌱 Creating new branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

echo "🔧 Setting up $LANGUAGE environment..."

# Language-specific setup
case "$LANGUAGE" in
    "rust")
        echo "🦀 Setting up Rust toolchain..."
        if command -v rustup >/dev/null 2>&1; then
            rustup update 2>/dev/null || echo "Warning: rustup update failed"
            rustup component add clippy rustfmt 2>/dev/null || echo "Warning: rustup components install failed"
        fi
        
        # Install security tools
        if command -v cargo >/dev/null 2>&1; then
            cargo install --quiet cargo-audit cargo-deny 2>/dev/null || echo "Warning: Some Rust security tools failed to install"
        fi
        
        # Create rust-security-scan utility
        cat > /usr/local/bin/rust-security-scan << 'EOF'
#!/bin/bash
echo "🦀 Running Rust security scan..."
cargo audit || echo "Warning: cargo audit failed"
cargo clippy -- -D warnings || echo "Warning: clippy failed" 
cargo deny check 2>/dev/null || echo "Warning: cargo deny failed"
EOF
        chmod +x /usr/local/bin/rust-security-scan
        ;;
        
    "python")
        echo "🐍 Setting up Python toolchain..."
        # Install Python security tools (keep existing logic)
        pip install --quiet bandit safety pip-audit 2>/dev/null || echo "Warning: Some Python security tools failed to install"
        ;;
        
    *)
        echo "⚠️  Unknown language: $LANGUAGE, defaulting to Python setup"
        pip install --quiet bandit safety pip-audit 2>/dev/null || echo "Warning: Some Python security tools failed to install"
        ;;
esac

echo "📁 Setting up documentation workspace..."
mkdir -p /tmp/claude_docs
echo "# Claude Agent Documentation Workspace" > /tmp/claude_docs/README.md
echo "This directory is used by Claude Code for scratch work, code analysis, and documentation." >> /tmp/claude_docs/README.md
echo "Files here are temporary and used for improving task accuracy and memory management." >> /tmp/claude_docs/README.md

echo "🤖 Starting Claude Code execution..."

# Handle secure API key loading
if [ -f "/run/secrets/anthropic_api_key" ]; then
    echo "🔐 Loading API key from secure file..."
    export ANTHROPIC_API_KEY=$(cat /run/secrets/anthropic_api_key)
elif [ -n "$ANTHROPIC_API_KEY_FILE" ] && [ -f "$ANTHROPIC_API_KEY_FILE" ]; then
    echo "🔐 Loading API key from specified file..."
    export ANTHROPIC_API_KEY=$(cat "$ANTHROPIC_API_KEY_FILE")
elif [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: No API key found. Expected file at /run/secrets/anthropic_api_key or ANTHROPIC_API_KEY environment variable."
    exit 1
fi

# Generate language-specific security tools info
if [ "$LANGUAGE" = "rust" ]; then
    SECURITY_TOOLS="Security tools: cargo-audit (vulnerabilities), cargo clippy -- -D warnings (lints), cargo deny check (policies), rust-security-scan (combined)"
elif [ "$LANGUAGE" = "python" ]; then
    SECURITY_TOOLS="Security tools: bandit -r . (security), safety check (vulnerabilities), pip-audit (dependencies)"
else
    SECURITY_TOOLS="Security tools: claude-security-scan scan"
fi

# Generate issue reference for PR creation
ISSUE_ARG=""
if [ -n "$GITHUB_ISSUE_NUMBER" ]; then
    ISSUE_ARG="--issue $GITHUB_ISSUE_NUMBER"
fi

# Build co-author attribution for git commits
CO_AUTHOR_LINE=""
if [ -n "\${DEFAULT_REVIEWER:-}" ]; then
    # Try to get reviewer's email from GitHub (fallback to generic)
    REVIEWER_EMAIL="\${DEFAULT_REVIEWER}@users.noreply.github.com"
    CO_AUTHOR_LINE="Co-authored-by: \${DEFAULT_REVIEWER:-vikranth22446} <$REVIEWER_EMAIL>"
fi

# Check if this is PR continuation mode
if [ -n "$PR_NUMBER" ]; then
    PR_WORKFLOW="After completing work, push changes and comment on PR:
python /usr/local/bin/github_utils.py comment-pr $PR_NUMBER \"✅ **Work Complete**

[Summary of changes made]

Please review the additional changes.\""
else
    PR_WORKFLOW="After completing work, create PR:
python /usr/local/bin/github_utils.py create-pr \"Fix: [brief title]\" \"[detailed summary of changes made]\" $ISSUE_ARG --reviewer \${DEFAULT_REVIEWER:-\"vikranth22446\"}"
fi

# Optimized prompt for cost efficiency  
CLAUDE_PROMPT="Complete task in $TASK_SPEC_FILE. Git ready: branch $BRANCH_NAME (base: $BASE_BRANCH).

Git workflow: git add . && git commit -m \"Auto-fix: [summary]

$CO_AUTHOR_LINE\" && git push -u origin $BRANCH_NAME

$PR_WORKFLOW

GitHub utils (python /usr/local/bin/github_utils.py):
- notify-progress \"step\" - Report progress
- notify-completion \"summary\" --reviewer \${DEFAULT_REVIEWER:-\"vikranth22446\"} - Mark complete (use AFTER updating PR)
- notify-error \"error\" - Report issues
- request-clarification \"question\" - Ask for help

$SECURITY_TOOLS

Use /tmp/claude_docs/ for analysis notes. Working dir: /workspace. Read only essential files to minimize cost."

# Start real-time cost monitoring
echo "📊 Starting cost monitoring..."
python3 /usr/local/bin/claude_cost_monitor.py start 30 &
COST_MONITOR_PID=$!

# Execute Claude with correct command
echo "🤖 Starting Claude execution..."
claude --dangerously-skip-permissions --print "$CLAUDE_PROMPT"
CLAUDE_EXIT_CODE=$?

# Stop cost monitoring and get final stats
echo "📊 Collecting final session statistics..."
kill $COST_MONITOR_PID 2>/dev/null || true

# Get final cost summary and save to shared directory
python3 /usr/local/bin/claude_cost_monitor.py summary

# Export cost data for job manager to pickup
if [ -f "/tmp/claude_cost_monitor.json" ]; then
    cp /tmp/claude_cost_monitor.json /tmp/cost_data/session_cost.json
    echo "💾 Cost data exported for job manager"
else
    echo "⚠️  No cost data file found"
fi

echo "✅ Claude execution completed (exit code: $CLAUDE_EXIT_CODE)"
exit $CLAUDE_EXIT_CODE