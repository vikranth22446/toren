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

# Set up GitHub token authentication for HTTPS git operations
echo "🔐 Setting up GitHub authentication..."

if [ -n "$GITHUB_TOKEN" ]; then
    echo "✅ Found GitHub token in environment"
    
    # Handle read-only .gitconfig by using a writable location
    export GIT_CONFIG_GLOBAL=/tmp/.gitconfig
    
    # Copy existing config if it exists
    if [ -f "/root/.gitconfig" ]; then
        cp /root/.gitconfig /tmp/.gitconfig 2>/dev/null || true
    fi
    
    # Set up git credential helper with the token
    git config --global credential.helper store
    
    # Create credential file manually (more reliable than piping to credential-store)
    mkdir -p /root
    echo "https://x-access-token:$GITHUB_TOKEN@github.com" > /root/.git-credentials
    echo "✅ GitHub HTTPS authentication configured"
    
    # GitHub CLI authentication via GITHUB_TOKEN environment variable
    echo "🔧 GitHub CLI will use GITHUB_TOKEN for authentication"
else
    echo "❌ No GitHub token found in environment"
    echo "❌ Git operations will fail - check token setup"
    exit 1
fi

echo "📥 Fetching latest changes..."
git fetch origin

echo "🌿 Checking out base branch: $BASE_BRANCH"
git checkout "$BASE_BRANCH"

echo "📡 Pulling latest changes from $BASE_BRANCH..."
git pull origin "$BASE_BRANCH"

echo "🌱 Setting up branch: $BRANCH_NAME"
if git show-ref --verify --quiet refs/heads/"$BRANCH_NAME"; then
    echo "✅ Branch $BRANCH_NAME already exists, checking out..."
    git checkout "$BRANCH_NAME"
    echo "📡 Pulling latest changes from remote branch..."
    git pull origin "$BRANCH_NAME" || echo "⚠️  Remote branch may not exist or no changes to pull"
else
    echo "🌱 Creating new branch: $BRANCH_NAME"
    git checkout -b "$BRANCH_NAME"
fi

# Record starting commit for git diff calculation at the end
STARTING_COMMIT=$(git rev-parse HEAD)
echo "📊 Recording starting commit for diff calculation: ${STARTING_COMMIT:0:8}"

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

# Handle Claude Code authentication
if [ -d "/root/.claude_mounted" ] && [ -n "$(ls -A /root/.claude_mounted 2>/dev/null)" ]; then
    echo "🔐 Setting up Claude Code session authentication..."
    # Copy mounted .claude directory to writable location
    cp -r /root/.claude_mounted /root/.claude
    chown -R root:root /root/.claude
    chmod -R 755 /root/.claude
    echo "✅ Claude Code configuration copied to writable location"
elif [ -n "$ANTHROPIC_API_KEY_FILE" ] && [ -f "$ANTHROPIC_API_KEY_FILE" ]; then
    echo "🔐 Loading API key from specified file..."
    export ANTHROPIC_API_KEY=$(cat "$ANTHROPIC_API_KEY_FILE")
elif [ -f "/tmp/claude_credentials.json" ]; then
    echo "🔐 Setting up ~/.claude.json for native Claude Code authentication"
    
    # Backup any existing .claude.json created by CLI installation
    if [ -f "/root/.claude.json" ]; then
        echo "📁 Backing up existing ~/.claude.json to ~/.claude.json.bak"
        cp /root/.claude.json /root/.claude.json.bak
    fi
    
    # Copy mounted credentials to proper location with correct permissions
    cp /tmp/claude_credentials.json /root/.claude.json
    chmod 600 /root/.claude.json
    
    echo "✅ Claude Code credentials configured (user's .claude.json preserved)"
    echo "📊 User config validation:"
    if grep -q "primaryApiKey" /root/.claude.json; then
        echo "   ✅ primaryApiKey found"
        if grep -q "sk-ant-" /root/.claude.json; then
            echo "   ✅ API key format valid"
        else
            echo "   ⚠️  API key format may be invalid"
        fi
    else
        echo "   ❌ primaryApiKey not found"
    fi
elif [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "🔐 Using ANTHROPIC_API_KEY environment variable"
else
    echo "❌ Error: No authentication found. Expected:"
    echo "   - Claude Code session: ~/.claude directory (recommended)"
    echo "   - API key file: /run/secrets/anthropic_api_key" 
    echo "   - Claude credentials: ~/.claude.json with primaryApiKey field"
    echo "   - API key env var: ANTHROPIC_API_KEY"
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

You should post updates after major steps via notify-progress and notify-completion commands.
GitHub utils (python /usr/local/bin/github_utils.py):
- notify-progress \"step\" - Report progress
- notify-completion \"summary\" --reviewer \${DEFAULT_REVIEWER:-\"vikranth22446\"} - Mark complete (use AFTER updating PR)
- notify-error \"error\" - Report issues
- request-clarification \"question\" - Ask for help

$SECURITY_TOOLS

Use /tmp/claude_docs/ for analysis notes. Working dir: /workspace. Read only essential files to minimize cost."

# Execute Claude with correct command first
echo "🤖 Starting Claude execution..."

# Start Claude in background and capture PID
IS_SANDBOX=1 claude --dangerously-skip-permissions "$CLAUDE_PROMPT" &
CLAUDE_PID=$!

# Find and tail Claude's log file to stream to Docker logs
echo "📋 Setting up log streaming..."

# Poll for Claude log file with timeout (40 seconds)
CLAUDE_LOG_FILE=""
for i in $(seq 1 40); do
    sleep 1
    CLAUDE_LOG_FILE=$(find /root/.claude/projects -name "*.jsonl" -type f 2>/dev/null | head -1)
    if [ -n "$CLAUDE_LOG_FILE" ] && [ -f "$CLAUDE_LOG_FILE" ]; then
        echo "📋 Found Claude log file after ${i} seconds: $CLAUDE_LOG_FILE"
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo "📋 Still waiting for Claude log file... (${i}s)"
    fi
done

if [ -n "$CLAUDE_LOG_FILE" ] && [ -f "$CLAUDE_LOG_FILE" ]; then
    echo "📋 Streaming Claude logs from: $CLAUDE_LOG_FILE"
    
    # Initialize cost tracking
    echo '{"total_cost": 0.0, "input_tokens": 0, "output_tokens": 0, "session_start": "'$(date -Iseconds)'"}' > /tmp/claude_cost_data.json
    
    # Tail the log file and format it for readability
    tail -f "$CLAUDE_LOG_FILE" | while IFS= read -r line; do
        # Extract and format key fields from JSONL for better readability
        echo "$line" | python3 -c "
import sys, json

try:
    line = sys.stdin.read().strip()
    if not line:
        exit()
    
    data = json.loads(line)
    
    # Handle new Claude Code JSONL format 
    if 'message' in data and data.get('type'):
        msg = data['message']
        msg_type = data.get('type')
        
        if msg_type == 'assistant':
            content = msg.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'text':
                        text = item.get('text', '')
                        if text and len(text.strip()) > 0:
                            print(f'🤖 Claude: {text}')
                    elif item.get('type') == 'tool_use':
                        tool_name = item.get('name', 'unknown')
                        tool_input = item.get('input', {})
                        if tool_name == 'Read':
                            file_path = tool_input.get('file_path', 'unknown')
                            print(f'📖 Reading: {file_path}')
                        elif tool_name == 'Edit':
                            file_path = tool_input.get('file_path', 'unknown')
                            print(f'✏️  Editing: {file_path}')
                        elif tool_name == 'Write':
                            file_path = tool_input.get('file_path', 'unknown')
                            print(f'📝 Writing: {file_path}')
                        elif tool_name == 'Bash':
                            desc = tool_input.get('description', '')
                            command = tool_input.get('command', '')
                            if desc:
                                print(f'⚡ Running: {desc}')
                            else:
                                print(f'⚡ Command: {command[:50]}...' if len(command) > 50 else f'⚡ Command: {command}')
                        elif tool_name == 'TodoWrite':
                            print(f'📝 Updated todo list')
                        elif tool_name == 'Grep':
                            pattern = tool_input.get('pattern', '')
                            print(f'🔍 Searching for: {pattern}')
                        elif tool_name == 'Glob':
                            pattern = tool_input.get('pattern', '')
                            print(f'🔍 Finding files: {pattern}')
                        else:
                            print(f'🔧 Tool: {tool_name}')
            
            # Handle usage info
            usage = msg.get('usage', {})
            if usage:
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                if input_tokens > 0 or output_tokens > 0:
                    print(f'💰 Tokens: {input_tokens} in, {output_tokens} out')
                    
                    # Update cost tracking file
                    import os
                    cost_file = '/tmp/claude_cost_data.json'
                    if os.path.exists(cost_file):
                        try:
                            with open(cost_file, 'r') as f:
                                cost_data = json.load(f)
                        except:
                            cost_data = {'total_cost': 0.0, 'input_tokens': 0, 'output_tokens': 0}
                    else:
                        cost_data = {'total_cost': 0.0, 'input_tokens': 0, 'output_tokens': 0}
                    
                    # Update token counts
                    cost_data['input_tokens'] += input_tokens  
                    cost_data['output_tokens'] += output_tokens
                    
                    # Update cost (Claude 3.5 Sonnet pricing: $3/1M input, $15/1M output tokens)
                    cost_data['total_cost'] += (input_tokens * 0.000003) + (output_tokens * 0.000015)
                    
                    # Save updated cost data
                    try:
                        with open(cost_file, 'w') as f:
                            json.dump(cost_data, f)
                    except:
                        pass
        
        elif msg_type == 'user':
            # Handle tool results  
            content = msg.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'tool_result':
                        result = item.get('content', '')
                        if result and 'error' not in result.lower() and len(result) < 100:
                            print(f'🔧 Tool result: {result}')
                        elif 'error' in result.lower():
                            print(f'❌ Tool error: {result[:100]}')
                        else:
                            print(f'🔧 Tool completed successfully')
    
    # Skip other internal entries silently
    
except Exception as e:
    # Only show error-related lines
    if line and ('error' in line.lower() or 'failed' in line.lower() or 'exception' in line.lower()):
        print(f'❌ {line[:200]}...' if len(line) > 200 else f'❌ {line}')
" 2>/dev/null || echo "📋 $line"
    done &
    LOG_TAIL_PID=$!
else
    echo "⚠️  Could not find Claude log file for streaming"
    LOG_TAIL_PID=""
fi

# Wait for Claude to complete
wait $CLAUDE_PID
CLAUDE_EXIT_CODE=$?

# Stop log tailing
if [ -n "$LOG_TAIL_PID" ]; then
    kill $LOG_TAIL_PID 2>/dev/null || true
fi

# Stop cost monitoring and get final stats
echo "📊 Collecting final session statistics..."
kill $COST_MONITOR_PID 2>/dev/null || true

# Generate final cost summary from our tracked data and git stats
python3 -c "
import json
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

# Load cost data from our tracking
cost_data = {'total_cost': 0.0, 'input_tokens': 0, 'output_tokens': 0}
cost_file = Path('/tmp/claude_cost_data.json')

if cost_file.exists():
    try:
        with open(cost_file, 'r') as f:
            cost_data = json.load(f)
    except:
        pass

# Get git statistics
git_stats = {'files_changed': 0, 'lines_added': 0, 'lines_deleted': 0, 'total_lines_changed': 0}

try:
    # Get diff stats against the starting commit to capture all changes made during this session
    starting_commit = '$STARTING_COMMIT'
    diff_result = subprocess.run(['git', 'diff', '--stat', starting_commit + '..HEAD'], capture_output=True, text=True)
    
    if diff_result.returncode == 0 and diff_result.stdout.strip():
        summary_line = diff_result.stdout.strip().split('\n')[-1]
        
        insertion_match = re.search(r'(\d+) insertion', summary_line)
        if insertion_match:
            git_stats['lines_added'] = int(insertion_match.group(1))
            
        deletion_match = re.search(r'(\d+) deletion', summary_line)  
        if deletion_match:
            git_stats['lines_deleted'] = int(deletion_match.group(1))
            
        files_match = re.search(r'(\d+) file', summary_line)
        if files_match:
            git_stats['files_changed'] = int(files_match.group(1))
            
    git_stats['total_lines_changed'] = git_stats['lines_added'] + git_stats['lines_deleted']
        
except:
    pass

# Create final session data
session_data = {
    'session_start': '$(date -Iseconds)',
    'last_update': datetime.now(timezone.utc).isoformat(),
    'cost': cost_data,
    'git_stats': git_stats,
    'summary': {
        'total_cost': cost_data['total_cost'],
        'total_tokens': cost_data['input_tokens'] + cost_data['output_tokens'],
        'input_tokens':  cost_data['input_tokens'],
        'output_tokens': cost_data['output_tokens'], 
        'lines_changed': git_stats['total_lines_changed'],
        'files_changed': git_stats['files_changed']
    }
}

# Print summary
print('📈 Current Session:')
print(f'  💰 Cost: \${session_data[\"summary\"][\"total_cost\"]:.4f}')
print(f'  🔤 Tokens: {session_data[\"summary\"][\"total_tokens\"]:,}')
print(f'  🔤 Input tokens: {session_data[\"summary\"][\"input_tokens\"]:,}')
print(f'  🔤 Output tokens: {session_data[\"summary\"][\"output_tokens\"]:,}')
print(f'  📝 Lines changed: {session_data[\"summary\"][\"lines_changed\"]}')
print(f'  📁 Files modified: {session_data[\"summary\"][\"files_changed\"]}')

# Save to monitoring location
with open('/tmp/claude_cost_monitor.json', 'w') as f:
    json.dump(session_data, f, indent=2)
"

# Export cost data for job manager to pickup
if [ -f "/tmp/claude_cost_monitor.json" ]; then
    cp /tmp/claude_cost_monitor.json /tmp/cost_data/session_cost.json
    echo "💾 Cost data exported for job manager"
else
    echo "⚠️  No cost data file found"
fi

echo "✅ Claude execution completed (exit code: $CLAUDE_EXIT_CODE)"
exit $CLAUDE_EXIT_CODE