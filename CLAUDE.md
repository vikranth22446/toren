# Claude Agent Runner

## Overview
Production-grade autonomous GitHub agent system that processes specifications, executes code changes, and creates pull requests with enterprise security controls.

## Architecture

### Refactored Components (69% code reduction)
- **`toren.py`** (846 lines) - Main orchestration and CLI interface
- **`input_validator.py`** (191 lines) - Input sanitization and validation  
- **`ai_cli_interface.py`** (162 lines) - Claude API interactions and cost estimation
- **`container_manager.py`** (318 lines) - Docker operations and image building
- **`ui_utilities.py`** (289 lines) - CLI dashboard, status display, and formatting
- **`github_utils.py`** (477 lines) - GitHub API operations and PR management
- **`job_manager.py`** (386 lines) - Background job lifecycle management

### Core Features
- **Execution Modes**: Synchronous (--disable-daemon) or background daemon jobs
- **Security**: Multi-layered input validation, secure credential mounting, path validation
- **Docker Integration**: Dynamic agent image building with layer caching
- **ML/AI Support**: GPU environments, custom volumes, model caching
- **GitHub Integration**: Issue processing, PR creation, progress notifications
- **Job Management**: Real-time monitoring, AI summaries, log following

## Usage

### Basic Commands
```bash
# Run task synchronously
python3 toren.py run --base-image python:3.11 --spec task.md --branch fix/bug --disable-daemon

# Run in background (default)
python3 toren.py run --base-image python:3.11 --issue https://github.com/user/repo/issues/123 --branch fix/issue-123

# Monitor jobs
python3 toren.py status
python3 toren.py logs job_id --follow
python3 toren.py summary job_id
python3 toren.py cleanup --all

# Health check with security scan
python3 toren.py health --docker-image python:3.11 --security
```

### ML/AI Workflows
```bash
# GPU + model caching
python3 toren.py run --base-image pytorch/pytorch:latest --spec ml_task.md --branch fix/training \
  --env CUDA_VISIBLE_DEVICES=0 --env HF_HOME=/cache/huggingface \
  --volume /data/models:/workspace/models --volume /cache:/root/.cache
```

## Security Features
- **Input Validation**: Regex patterns, allowlists, length limits
- **Credential Management**: Read-only file mounting (not environment variables)
- **Path Security**: Directory allowlisting, traversal protection
- **Container Security**: Resource cleanup, proper exception handling
- **Race Prevention**: File locking for atomic operations
- **Automated Scanning**: Git diff analysis, Docker vulnerability scanning, pre-commit hooks

## Container Workflow
1. **Image Building**: Dynamic agent-enabled images from base images with security tools
2. **Secure Execution**: Read-only credential mounting, validated path mounting
3. **Progress Tracking**: Real-time GitHub notifications via `github_utils.py`
4. **Cleanup**: Automatic container and temporary file removal

## Multi-CLI Architecture
Designed as generic AI CLI runner with minimal coupling:
- **CLI-Specific**: Command syntax, authentication formats (easily configurable)
- **Generic Core**: Docker orchestration, Git workflows, security, job management
- **Extensible**: Can support Gemini, Cursor, Qwen with configuration changes

## File Structure
```
claude_agent_runner/
├── toren.py           # Main orchestration (846 lines, 69% reduction)
├── input_validator.py        # Validation logic
├── ai_cli_interface.py       # Claude API interface  
├── container_manager.py      # Docker operations
├── ui_utilities.py           # CLI utilities and dashboard
├── github_utils.py           # GitHub API integration
├── job_manager.py           # Background job management
├── container_entrypoint.sh  # Container initialization
└── scripts/                 # Security scanning utilities
    ├── scan_diff.sh         # Fast git diff security scan
    ├── install-hooks.sh     # Pre-commit security hooks
    └── run_security_scan.sh # Full security analysis
```

## Benefits
- ✅ **Clean Architecture**: 69% code reduction with proper separation of concerns
- ✅ **Production Security**: Enterprise-grade security with automated vulnerability scanning
- ✅ **Fast Execution**: Docker layer caching and optimized performance
- ✅ **Flexible Deployment**: Sync/async modes with ML/AI environment support
- ✅ **Comprehensive Monitoring**: Real-time tracking, AI summaries, cost analysis
- ✅ **Multi-CLI Ready**: Generic architecture supporting multiple AI CLIs