# Test Task for Claude Agent

## Overview
This is a simple test task to verify that the Claude Agent Runner can handle both Python and Rust projects.

## Requirements
- Add a simple "Hello World" function to the project
- Ensure it follows language-specific best practices
- Run security scanning

## Python Version
```python
def hello_world():
    """Return a friendly greeting."""
    return "Hello, World from Claude Agent!"

if __name__ == "__main__":
    print(hello_world())
```

## Rust Version
```rust
fn hello_world() -> String {
    "Hello, World from Claude Agent!".to_string()
}

fn main() {
    println!("{}", hello_world());
}
```

## Acceptance Criteria
- Function is properly implemented
- Code follows language conventions
- Security scan passes
- Tests can be executed