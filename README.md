# Toren - Multi-AI CLI Agent Runner

Toren is an autonomous containerized agent runner that simplifies staying in deep work while using AI agents. Most AI coding tools are useful in short bursts, but take you away from deep focus. They need constant checking as if working with a junior dev.

Toren is built on the assumption that AI should work as an autonomous agent in our existing local environment.

The hard parts of using AI agents for my use cases:
- Getting them access to the same resources you use — GPUs, model checkpoints, and a proper setup.
- Writing clear, accurate specs so the output is easy to trust and easy to review.

By focusing on writing specifications, you can take ownership and better understand the changes AI will make. 

Using AI agents in async agent environments should be containerized to prevent security issues. Automated security scans should be run since it's hard to fully trust AI generated code.

CLI tools are also becoming more common, and Toren makes it easy to swap tools or work directly inside your local dev setup.

Compared to tools like:
- LangChain Open-SWE — Requires using LangChain services and Daytona for development. Also a local cli tool to manage all of it
- Claude Code / Gemini — Pull you out of flow to verify steps and requires opening multiple copies of the codebase for multiple tasks.
- Cursor — Great integration but constantly dictates the next edit, which interrupts your own thinking. For multiple tasks, you need multiple copies of the codebase
- Claude as a GitHub user — Writing full specs in GitHub is cumbersome; providing them directly is simpler. Setting up with local models/checkpoints is also easier with local Docker abstraction. You are also billed on github action minutes

# General Screenshots
![alt text](demo_images/image.png)
![alt text](demo_images/image-1.png)
![alt text](demo_images/image-2.png)
![alt text](demo_images/image-3.png)

Most of this code was AI-generated, but I do go through/refactor and fix it. It cost around $100 to make. 


## Features

- **Multi-AI Support**: Works with Claude, Gemini, and extensible to other AI CLIs
- **Docker-based Execution**: Secure, isolated environments with custom base images  
- **Security** some automated security checks
- **Job Management**: Background execution, real-time monitoring, cost tracking
- **GitHub Integration**: Issue processing, PR creation, progress notifications
- **ML/AI**: Can use local resources for quick dev

## Quick Start

### Installation

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
Install Docker, Your CLI of choice(mainly claude code rn)

For the specific codebase, mount the directory and point to the /workspace section.

```bash
WORKDIR /workspace
COPY . /workspace/
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
```

## Configuration

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

# Setting up the local docker image
Mount the current code into a folder with /workspace

## Lint
bash scripts/quality-check.sh. Runs mypy and flake8


# Demo Commands
