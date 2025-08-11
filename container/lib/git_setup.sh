#!/bin/bash
# Git workspace setup module

setup_git_workspace() {
    local base_branch="$1"
    local branch_name="$2"
    
    echo "🔄 Setting up git workspace..."
    
    # Copy mounted gitconfig to writable location if it exists
    if [ -f /root/.gitconfig ]; then
        cp /root/.gitconfig /tmp/gitconfig
        export GIT_CONFIG_GLOBAL=/tmp/gitconfig
    fi
    
    # Ensure credential helper is configured (in case it wasn't set in auth setup)
    if [ -z "$(git config credential.helper)" ]; then
        echo "🔧 Configuring Git credential helper"
        git config --global credential.helper store
    fi
    
    # Configure git - prioritize environment variables from host
    if [ -n "$GIT_AUTHOR_NAME" ]; then
        echo "📝 Using Git username from host: $GIT_AUTHOR_NAME"
        git config user.name "$GIT_AUTHOR_NAME"
    elif [ -n "$GITHUB_USERNAME" ]; then
        echo "📝 Using GitHub username for Git: $GITHUB_USERNAME"
        git config user.name "$GITHUB_USERNAME"
    elif [ -z "$(git config user.name)" ]; then
        git config user.name "Claude Agent"
    fi
    
    if [ -n "$GIT_AUTHOR_EMAIL" ]; then
        echo "📧 Using Git email from host: $GIT_AUTHOR_EMAIL"
        git config user.email "$GIT_AUTHOR_EMAIL"
    elif [ -z "$(git config user.email)" ]; then
        git config user.email "claude-agent@anthropic.com"
    fi
    
    # Change to workspace directory
    cd /workspace
    
    # Ensure remote URL is HTTPS for token authentication
    current_url=$(git remote get-url origin)
    if [[ $current_url == git@github.com:* ]]; then
        https_url="https://github.com/${current_url#git@github.com:}"
        git remote set-url origin "$https_url"
        echo "🔄 Converted SSH remote to HTTPS: $https_url"
    fi
    
    echo "📥 Fetching latest changes..."
    echo "🔍 Debug: Git credential helper: $(git config credential.helper)"
    echo "🔍 Debug: Git credentials file exists: $(test -f /root/.git-credentials && echo 'YES' || echo 'NO')"
    echo "🔍 Debug: Git credentials file contents: $(test -f /root/.git-credentials && head -c 50 /root/.git-credentials || echo 'FILE NOT FOUND')"
    echo "🔍 Debug: Remote URL: $(git remote get-url origin)"
    git fetch origin
    
    echo "🌿 Checking out base branch: $base_branch"
    git checkout "$base_branch"
    
    echo "📡 Pulling latest changes from $base_branch..."
    git pull origin "$base_branch"
    
    echo "🌱 Setting up branch: $branch_name"
    if git show-ref --verify --quiet refs/heads/"$branch_name"; then
        echo "✅ Branch $branch_name exists, checking out..."
        git checkout "$branch_name"
        echo "📡 Pulling latest changes from remote branch..."
        git pull origin "$branch_name" || echo "⚠️  Remote branch may not exist"
    else
        echo "🌱 Creating new branch: $branch_name"
        git checkout -b "$branch_name"
    fi
}