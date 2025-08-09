FROM ubuntu:22.04

# Install basic dependencies and Node.js (required for Claude CLI)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create the .local/bin directory first
RUN mkdir -p /root/.local/bin

# Install Claude Code CLI and ensure it's in PATH
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc

# Make sure claude is executable and in PATH for this session
ENV PATH="/root/.local/bin:$PATH"

# Simple test script
COPY test-claude-auth.sh /test-claude-auth.sh
RUN chmod +x /test-claude-auth.sh

CMD ["/test-claude-auth.sh"]