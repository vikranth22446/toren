#!/bin/bash
# Authentication setup module

setup_authentication() {
    local ai_provider="$1"
    
    echo "🔐 Setting up authentication for $ai_provider..."
    
    # GitHub token authentication
    setup_github_auth
    
    # AI provider authentication
    case "$ai_provider" in
        "claude")
            setup_claude_auth
            ;;
        "gpt")
            setup_openai_auth
            ;;
        *)
            echo "⚠️  Unknown AI provider: $ai_provider"
            setup_claude_auth  # fallback
            ;;
    esac
}

setup_github_auth() {
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "✅ Found GitHub token"
        
        # Handle read-only .gitconfig
        export GIT_CONFIG_GLOBAL=/tmp/.gitconfig
        
        if [ -f "/root/.gitconfig" ]; then
            cp /root/.gitconfig /tmp/.gitconfig 2>/dev/null || true
        fi
        
        git config --global credential.helper store
        # Force HTTPS for GitHub to prevent SSH fallback
        git config --global url."https://github.com/".insteadOf "git@github.com:"
        git config --global url."https://github.com/".insteadOf "ssh://git@github.com/"
        mkdir -p /root
        
        # Use actual GitHub username if available, otherwise use x-access-token
        if [ -n "$GITHUB_USERNAME" ]; then
            echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" > /root/.git-credentials
            echo "📝 Using GitHub username: $GITHUB_USERNAME"
        else
            echo "https://x-access-token:$GITHUB_TOKEN@github.com" > /root/.git-credentials
            echo "📝 Using token-based authentication"
        fi
        echo "✅ GitHub HTTPS authentication configured"
    else
        echo "❌ No GitHub token found - git operations will fail"
        exit 1
    fi
}

setup_claude_auth() {
    found_creds=false
    if [ -f "/tmp/claude_credentials.json" ]; then
        echo "🔐 Setting up ~/.claude.json..."
        cp /tmp/claude_credentials.json /root/.claude.json
        chmod 600 /root/.claude.json
        echo "✅ Claude Code credentials configured"
        found_creds=true;
    fi

    if [ -d "/root/.claude_mounted" ] && [ -n "$(ls -A /root/.claude_mounted 2>/dev/null)" ]; then
        echo "🔐 Setting up Claude Code session authentication..."
        cp -r /root/.claude_mounted/. /root/.claude
        chown -R root:root /root/.claude
        chmod -R 755 /root/.claude
        echo "✅ Claude Code configuration copied"
        found_creds=true;
    elif [ -n "$ANTHROPIC_API_KEY_FILE" ] && [ -f "$ANTHROPIC_API_KEY_FILE" ]; then
        echo "🔐 Loading API key from file..."
        found_creds=true;
        export ANTHROPIC_API_KEY=$(cat "$ANTHROPIC_API_KEY_FILE")
    elif [ -n "$ANTHROPIC_API_KEY" ]; then
        echo "🔐 Using ANTHROPIC_API_KEY environment variable"
        found_creds=true;
    fi
    
    if [ "$found_creds" = true ]; then
        echo "✅ Claude authentication found"
    else
        echo "❌ No Claude authentication found"
        exit 1
    fi
}

setup_openai_auth() {
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "✅ OpenAI API key configured"
    else
        echo "❌ No OpenAI API key found"
        exit 1
    fi
}