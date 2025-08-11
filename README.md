# Toren - Multi-AI CLI Agent Runner

**Toren** is a production-grade autonomous GitHub agent system that can work with multiple AI CLIs (Claude, Gemini, and more). It processes specifications, executes code changes, and creates pull requests with enterprise security controls.

testing from claude

## Features

- 🤖 **Multi-AI Support**: Works with Claude, Gemini, and extensible to other AI CLIs
- 🐳 **Docker-based Execution**: Secure, isolated environments with custom base images  
- 🔒 **Enterprise Security**: Input validation, credential management, vulnerability scanning
- 📊 **Job Management**: Background execution, real-time monitoring, cost tracking
- 🔗 **GitHub Integration**: Issue processing, PR creation, progress notifications
- 🏗️ **ML/AI Ready**: GPU support, model caching, custom environments

## Quick Start

### Installation

```bash
# Clone and install
git clone <repository_url>
cd toren
chmod +x install.sh
./install.sh
```

Or install manually:
```bash
pip install -e .
```

### Basic Usage

```bash
# Check help
toren --help
toren run --help

# Run with Claude (default)
toren run --base-image python:3.11 --spec task.md --branch fix/bug

# Run with Gemini
toren run --cli-type gemini --base-image python:3.11 --spec task.md --branch fix/bug

# Process GitHub issue
toren run --issue https://github.com/user/repo/issues/123 --branch fix/issue-123

# Monitor jobs
toren status
toren logs job_id --follow
toren summary job_id

# Health check
toren health --docker-image python:3.11 --security
```

### ML/AI Workflows

```bash
# GPU + model caching
toren run --base-image pytorch/pytorch:latest --spec ml_task.md --branch fix/training \
  --env CUDA_VISIBLE_DEVICES=0 --env HF_HOME=/cache/huggingface \
  --volume /data/models:/workspace/models --volume /cache:/root/.cache
```

## Prerequisites

- **Python 3.8+**
- **Docker** (with access to run containers)
- **AI CLI credentials**:
  - Claude: `~/.claude.json` or `ANTHROPIC_API_KEY` environment variable
  - Gemini: `GEMINI_API_KEY` environment variable
- **GitHub Token**: `GITHUB_TOKEN` environment variable (for GitHub operations)

## Configuration

### AI CLI Setup

**Claude:**
```bash
# Option 1: Install Claude CLI and configure
curl -fsSL https://claude.ai/install.sh | bash
# Then follow Claude CLI setup

# Option 2: Set environment variable
export ANTHROPIC_API_KEY=your_key_here
```

**Gemini:**
```bash
# Install Gemini CLI
npm install -g @google/generative-ai-cli

# Set environment variable  
export GEMINI_API_KEY=your_key_here
```

**GitHub:**
```bash
export GITHUB_TOKEN=your_github_token
```

## Commands

| Command | Description |
|---------|-------------|
| `toren run` | Start new AI agent job |
| `toren status` | Show job status and progress |
| `toren logs` | Show job logs and output |
| `toren summary` | Show AI-generated task summary |
| `toren cleanup` | Clean up completed jobs |
| `toren kill` | Kill running job immediately |
| `toren health` | Run system health checks |

## Key Options

- `--cli-type {claude,gemini}`: Choose AI CLI to use
- `--base-image IMAGE`: Docker base image for execution
- `--spec FILE`: Markdown specification file
- `--issue URL`: GitHub issue to process
- `--branch NAME`: Git branch name to create
- `--env VAR=VALUE`: Environment variables
- `--volume HOST:CONTAINER`: Volume mounts
- `--language {python,rust}`: Project language
- `--cost-estimate`: Estimate AI API costs

## Security Features

- 🔐 **Input Validation**: Regex patterns, allowlists, length limits
- 🗂️ **Credential Management**: Read-only file mounting (not environment variables)
- 🛡️ **Path Security**: Directory allowlisting, traversal protection  
- 🔍 **Container Security**: Resource cleanup, vulnerability scanning
- 🔒 **Race Prevention**: File locking for atomic operations

## Architecture

Toren is designed as a generic AI CLI runner with minimal coupling:

- **CLI-Specific**: Command syntax, authentication formats (easily configurable)
- **Generic Core**: Docker orchestration, Git workflows, security, job management
- **Extensible**: Can support additional AI CLIs with configuration changes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

## Lint
bash scripts/quality-check.sh. Runs mypy and flake8

## License

MIT License - see LICENSE file for details.