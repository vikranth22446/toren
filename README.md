# Claude Agent Runner

Autonomous GitHub Issue/Spec Processor that reads specifications and creates pull requests automatically.

## Table of Contents

- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Basic Usage Examples](#basic-usage-examples)
  - [Managing Background Jobs](#managing-background-jobs)
  - [Your First Task](#your-first-task)
- [Features](#features)
- [Advanced Usage](#advanced-usage)
- [Docker Usage](#docker-usage)
- [Requirements](#requirements)
- [Workflow](#workflow)
- [Safety Features](#safety-features)
- [Configuration](#configuration)

## Quick Start

### Prerequisites

Before using Claude Agent Runner, ensure you have:

1. **Python 3.11+** installed
2. **Docker** installed and running
3. **Git** configured with push access to your repository
4. **GitHub CLI (`gh`)** installed and authenticated
5. **Claude Code CLI** installed
6. **Anthropic API Key** set as environment variable

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd claude-agent-runner
   ```

2. **Set up your environment:**
   ```bash
   # Set your Anthropic API key
   export ANTHROPIC_API_KEY="your-api-key-here"
   
   # Authenticate GitHub CLI (if not already done)
   gh auth login
   ```

3. **Verify installation:**
   ```bash
   # Check that all tools are available
   python3 --version    # Should be 3.11+
   docker --version     # Should show Docker version
   gh --version         # Should show GitHub CLI version
   claude --version     # Should show Claude Code CLI version
   ```

### Basic Usage Examples

#### 1. Process a Local Specification File
```bash
# Create a simple task specification
echo "Fix the login bug in the authentication module" > task.md

# Run the agent (background mode - default)
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch fix/login-bug

# Check job status
python3 claude_agent.py status
```

#### 2. Process a GitHub Issue
```bash
# Process an existing GitHub issue
python3 claude_agent.py run \
  --base-image myproject:dev \
  --issue https://github.com/owner/repo/issues/123 \
  --branch fix/issue-123
```

#### 3. Synchronous Execution (Wait for Completion)
```bash
# Run in foreground mode (no background daemon)
python3 claude_agent.py run \
  --base-image python:3.11 \
  --spec task.md \
  --branch fix/login-bug \
  --disable-daemon
```

#### 4. Custom Configuration
```bash
# With custom base branch and reviewer
python3 claude_agent.py run \
  --base-image python:3.11 \
  --spec task.md \
  --branch feature/new-feature \
  --base-branch develop \
  --reviewer @yourteammate
```

### Managing Background Jobs

Once you start a background job, use these commands to monitor and manage it:

```bash
# View all jobs
python3 claude_agent.py status

# View specific job details
python3 claude_agent.py status --job-id abc123

# Get AI-generated job summary
python3 claude_agent.py summary abc123

# Watch real-time logs
python3 claude_agent.py logs abc123 --follow

# Clean up completed jobs
python3 claude_agent.py cleanup

# Kill a running job if needed
python3 claude_agent.py kill abc123
```

### Your First Task

Here's a complete example to get you started:

1. **Create a simple task file:**
   ```bash
   cat > my-first-task.md << 'EOF'
   # My First Task
   
   Add a simple "Hello World" function to the main module:
   - Create a function called `hello_world()` 
   - It should return the string "Hello, World!"
   - Add a simple test for this function
   EOF
   ```

2. **Run the agent:**
   ```bash
   python3 claude_agent.py run \
     --base-image python:3.11 \
     --spec my-first-task.md \
     --branch feature/hello-world
   ```

3. **Monitor progress:**
   ```bash
   # Check status
   python3 claude_agent.py status
   
   # View logs (replace abc123 with your actual job ID)
   python3 claude_agent.py logs abc123
   ```

4. **Review the results:**
   - The agent will create a new branch `feature/hello-world`
   - Make the requested changes to your codebase
   - Create a pull request with the changes
   - Add progress comments to track the work

## Features

- Read local markdown specifications and/or GitHub issues
- Execute Claude Code to implement solutions
- Validate code changes (300-400 line limit)
- Safety checks for privacy/security concerns
- Automatic branch creation and PR submission
- Progress tracking via GitHub comments
- Auto-tag reviewers when complete

## Advanced Usage

### Command-Line Interface Options

#### Background Mode Commands (Default)
```bash
# Launch job in background (daemon mode is default)
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123
python3 claude_agent.py run --base-image myproject:dev --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123

# With custom base branch (defaults to main)
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --base-branch develop

# With custom reviewer
python3 claude_agent.py run --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --reviewer @username
```

#### Legacy Direct Execution (Synchronous)
```bash
# Direct execution without background daemon
python3 claude_agent.py --base-image python:3.11 --spec task.md --branch feature/fix-issue-123
python3 claude_agent.py --base-image myproject:dev --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123
python3 claude_agent.py --base-image ubuntu:22.04 --spec task.md --issue https://github.com/owner/repo/issues/123 --branch feature/fix-issue-123

# With custom base branch (defaults to main)
python3 claude_agent.py --base-image python:3.11 --spec task.md --branch feature/fix-issue-123 --base-branch develop
```

#### Dashboard Commands (Job Management)
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

#### Backward Compatibility
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
