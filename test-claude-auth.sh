#!/bin/bash
echo "🧪 Testing Claude Code Authentication..."

echo ""
echo "📁 Checking if ~/.claude_mounted exists..."
if [ -d "/root/.claude_mounted" ]; then
    echo "✅ ~/.claude_mounted found"
    echo "📂 Contents:"
    ls -la /root/.claude_mounted/
    
    echo ""
    echo "🔄 Copying to ~/.claude..."
    # Remove any existing ~/.claude first
    rm -rf /root/.claude
    # Copy the mounted directory contents (not the directory itself)
    cp -r /root/.claude_mounted /root/.claude
    chown -R root:root /root/.claude
    chmod -R 755 /root/.claude
    
    echo "✅ Copy complete"
    echo "📂 ~/.claude contents:"
    ls -la /root/.claude/
    
    if [ -f "/root/.claude/settings.json" ]; then
        echo ""
        echo "⚙️ Claude settings.json contents:"
        cat /root/.claude/settings.json | head -10
    fi
    
    if [ -d "/root/.claude/projects" ]; then
        echo ""
        echo "📁 Projects directory:"
        ls -la /root/.claude/projects/ | head -5
    fi
else
    echo "❌ ~/.claude_mounted not found"
fi

echo ""
echo "🤖 Testing Claude Code CLI..."

# Fix PATH
export PATH="/root/.local/bin:$PATH"
echo "PATH: $PATH"

# Check if claude exists
if command -v claude >/dev/null 2>&1; then
    echo "✅ Claude CLI found"
    echo "Version check:"
    claude --version
    
    echo ""
    echo "Auth status test:"
    IS_SANDBOX=1 claude --print "Hello, this is a test. Just respond with 'Authentication working!'" 2>&1 | head -10
else
    echo "❌ Claude CLI still not found"
    echo "Looking for claude binary everywhere:"
    find / -name "claude" -type f 2>/dev/null | head -10 || echo "No claude binary found"
    echo ""
    echo "Checking common locations:"
    ls -la /root/.local/bin/ 2>/dev/null || echo "/root/.local/bin/ not found"
    ls -la /usr/local/bin/ | grep claude || echo "No claude in /usr/local/bin/"
    ls -la /usr/bin/ | grep claude || echo "No claude in /usr/bin/"
fi