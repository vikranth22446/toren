# Claude Agent Runner

Autonomous GitHub Issue/Spec Processor that reads specifications and creates pull requests automatically.

## Features

- Read local markdown specifications and/or GitHub issues
- Execute Claude Code to implement solutions
- Validate code changes (300-400 line limit)
- Safety checks for privacy/security concerns
- Automatic branch creation and PR submission
- Progress tracking via GitHub comments
- Auto-tag reviewers when complete

## Usage

### Basic Usage
```bash
python3 claude_agent.py --base-image python:3.11 --spec task.md --branch feature/fix-issue-123
python3 claude_agent.py --base-image myproject:dev --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123
python3 claude_agent.py --base-image ubuntu:22.04 --spec task.md --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123

# With custom base branch (defaults to main)
python3 claude_agent.py --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --base-branch develop
```

### Basic Usage (Background Mode - Default)
```bash
# Launch job in background (daemon mode is default)
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123
python3 claude_agent.py run --base-image myproject:dev --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123

# With custom base branch (defaults to main)
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --base-branch develop

# With custom reviewer
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --reviewer @username
```

### Dashboard Commands (All in One CLI)
```bash
# Check job status
python3 claude_agent.py status
python3 claude_agent.py status --job-id abc123
python3 claude_agent.py status --filter running

# View detailed job info
python3 claude_agent.py summary abc123

# Watch logs in real-time
python3 claude_agent.py logs abc123 --follow

# Clean up completed jobs
python3 claude_agent.py cleanup --all
python3 claude_agent.py cleanup --job-id abc123

# Kill running job
python3 claude_agent.py kill abc123
```

### Backward Compatibility
```bash
# Still works (defaults to 'run' command)
python3 claude_agent.py --base-image python:3.11 --spec task.md --branch feature/fix-issue-123
```

### Docker Usage

Build the container:
```bash
docker build -t claude-agent .
```

Run with credentials:
```bash
docker run \
  -v ~/.gitconfig:/root/.gitconfig \
  -v ~/.ssh:/root/.ssh \
  -v ~/.config/gh:/root/.config/gh \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  claude-agent \
  --spec /workspace/task.md --branch feature/fix-issue-123
```

## Requirements

- Python 3.11+
- Git configured with push access
- GitHub CLI (`gh`) authenticated
- Claude Code CLI installed
- `ANTHROPIC_API_KEY` environment variable

## Workflow

1. **Input Validation** - Validates spec files, GitHub URLs, branch names
2. **Safety Check** - Scans for security/privacy concerns
3. **Branch Creation** - Creates new git branch
4. **Task Execution** - Runs Claude Code with merged specification
5. **Change Validation** - Checks line count and change quality
6. **PR Creation** - Commits, pushes, and creates pull request
7. **Notification** - Comments on GitHub issue/PR with status updates

## Safety Features

- **Docker-only execution**: All code runs in isolated containers (no local execution)
- **Base image required**: Must specify `--base-image` for security
- Blocks execution if privacy/security keywords detected
- Enforces 300-400 line change limits
- Tags reviewer for manual review on failures
- Validates branch names and GitHub URLs
- Follows existing code style and patterns

## Configuration

Edit `claude_agent.py` to customize:
- `reviewer_username`: Default reviewer
- `max_lines`: Maximum lines changed (400)
- `warn_lines`: Warning threshold (300)

---
*This line was added by Claude to test the automated PR workflow.*
