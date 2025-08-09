# Claude Agent Runner Testing Plan
*Comprehensive incremental testing - Total time budget: ~3.5 hours*

## Phase 1: GitHub Integration Testing (50 minutes)

**Tests:**
- [x] **Comment on issue**: `python github_utils.py comment-issue 1 "Test comment"`
- [x] **Get issue details**: `python github_utils.py get-issue 1`
- [x] **Progress notification**: `python github_utils.py notify-progress "Testing phase" --details "Basic functionality"`
- [x] **Status update**: `python github_utils.py update-status "Running tests"`

**Expected Results:**
- Comments appear on GitHub issue
- Issue details returned as JSON
- No errors in execution

### 1.2 PR Creation Testing (15 minutes)
**Tests:**
- [ ] **Create test branch**: `git checkout -b test-pr-creation`
- [ ] **Make small change**: `echo "# Test" > test_file.md && git add . && git commit -m "Test commit"`
- [ ] **Push branch**: `git push -u origin test-pr-creation`
- [ ] **Test PR creation**: `python github_utils.py create-pr "Test PR" "Testing PR creation functionality" --issue 1 --reviewer vikranth22446`

**Expected Results:**
- PR created successfully with proper template
- Issue linked with "Closes #1"  
- Reviewer tagged
- Co-author attribution visible

### 1.3 NEW: PR Comment Processing (20 minutes)
**Setup:**
```bash
# Create a test PR with @claude mentions
git checkout -b test-pr-comments
echo "# PR Comment Test" > pr_test.md && git add . && git commit -m "Initial commit for PR testing"
git push -u origin test-pr-comments
gh pr create --title "Test PR for @claude mentions" --body "This PR is for testing @claude comment processing"
```

**Tests:**
- [ ] **Add @claude comment**: Comment on the PR: "@claude please add error handling to this function"
- [ ] **Test comment retrieval**: `python github_utils.py get-pr-comments [PR_NUMBER]`
- [ ] **Test task extraction**: `python github_utils.py extract-pr-tasks [PR_NUMBER]`
- [ ] **Test multiple @claude comments**: Add 2-3 more comments mentioning @claude
- [ ] **Verify filtering**: Ensure only @claude comments are returned

**Expected Results:**
- Only comments mentioning @claude are returned
- Task specification generated includes PR context
- Recent comments prioritized
- Proper JSON structure for comment data

### 1.4 Error Handling Testing (10 minutes)
**Tests:**
- [ ] **Invalid issue**: `python github_utils.py get-issue 99999`
- [ ] **Invalid PR**: `python github_utils.py get-pr-comments 99999`
- [ ] **Malformed commands**: Test missing parameters
- [ ] **Empty PR comments**: Test PR with no @claude mentions

**Expected Results:**
- Graceful error messages
- No crashes or exceptions
- Proper exit codes
- Clear feedback for missing @claude mentions

---

## Phase 2: PR Continuation Workflow Testing (45 minutes)

### 2.1 CLI Validation Testing (10 minutes)
**Tests:**
- [ ] **Multiple inputs**: `python3 claude_agent.py run --spec test.md --issue 1 --pr 42` (should fail)
- [ ] **PR number validation**: `python3 claude_agent.py run --pr invalid-pr-format` (should fail)
- [ ] **PR URL validation**: `python3 claude_agent.py run --pr https://github.com/user/repo/pull/42` (should extract number)
- [ ] **Valid PR number**: `python3 claude_agent.py run --base-image python:3.9 --pr 42` (validation should pass)

**Expected Results:**
- Proper validation of mutually exclusive options
- PR numbers extracted from URLs correctly
- Clear error messages for invalid formats

### 2.2 PR Branch Detection (15 minutes)
**Setup:**
```bash
# Use the test PR created in Phase 1.3
PR_NUMBER=$(gh pr list --limit 1 --json number --jq '.[0].number')
echo "Testing with PR #$PR_NUMBER"
```

**Tests:**
- [ ] **Branch detection**: Verify PR branch is detected and used automatically
- [ ] **Existing branch checkout**: Test that the system uses existing PR branch
- [ ] **Task spec generation**: Verify PR comments are converted to actionable tasks
- [ ] **Container environment**: Check that PR_NUMBER environment variable is set

**Expected Results:**
- PR branch automatically detected and used
- No new branch creation attempted
- Task specification includes PR context and @claude comments
- Container receives PR context

### 2.3 PR Comment Integration Testing (20 minutes)
**Setup:**
```bash
# Add more @claude comments to test PR
gh pr comment $PR_NUMBER --body "@claude please add input validation for the function parameters"
gh pr comment $PR_NUMBER --body "@claude also add comprehensive error messages"
gh pr comment $PR_NUMBER --body "This is a regular comment without @claude mentions"
```

**Tests:**
- [ ] **Full PR workflow**: `python3 claude_agent.py run --base-image python:3.9 --pr $PR_NUMBER --disable-daemon`
- [ ] **Task parsing**: Verify all @claude comments are included in task spec
- [ ] **Comment filtering**: Verify non-@claude comments are excluded
- [ ] **Progress updates**: Check if progress updates post as PR comments
- [ ] **Co-author commits**: Verify commits include co-author attribution

**Expected Results:**
- All @claude comments processed into actionable tasks
- Non-@claude comments filtered out
- Progress posted as PR comments instead of issue comments
- Commits maintain co-author attribution
- PR updated with additional commits (not new PR created)

---

## Phase 3: Docker & Container Testing (40 minutes)

### 3.1 Image Building (10 minutes)
**Tests:**
- [ ] **Health check**: `python3 claude_agent.py health --docker-image python:3.9`
- [ ] **Image build test**: `python3 claude_agent.py health --docker-image python:3.9` (should build agent image)
- [ ] **Multi-language support**: `python3 claude_agent.py health --docker-image rust:1.70 --language rust`

**Expected Results:**
- Agent images build successfully
- Language-specific toolchains detected
- No Docker errors

### 3.2 NEW: Cost Estimation Testing (15 minutes)
**Setup:**
```bash
# Create test specifications for cost estimation
cat > simple_task.md << 'EOF'
# Simple Task
Add a hello world function to the main.py file
EOF

cat > complex_task.md << 'EOF'
# Complex Task  
Refactor the entire authentication system:
1. Implement OAuth2 with multiple providers
2. Add comprehensive error handling
3. Create detailed unit tests
4. Add integration tests
5. Update documentation
6. Migrate existing user data
EOF
```

**Tests:**
- [ ] **Simple task cost estimation**: `python3 claude_agent.py run --base-image python:3.9 --spec simple_task.md --branch test/simple --cost-estimate`
- [ ] **Complex task cost estimation**: `python3 claude_agent.py run --base-image python:3.9 --spec complex_task.md --branch test/complex --cost-estimate`
- [ ] **PR continuation cost estimation**: `python3 claude_agent.py run --base-image python:3.9 --pr $PR_NUMBER --cost-estimate`
- [ ] **Language comparison**: `python3 claude_agent.py run --base-image rust:1.70 --spec simple_task.md --branch test/rust-simple --language rust --cost-estimate`
- [ ] **No API key test**: Test with unset ANTHROPIC_API_KEY
- [ ] **User cancellation test**: Choose "n" when prompted to continue

**Expected Results:**
- Simple tasks show lower estimated costs ($0.01-0.05)
- Complex tasks show higher estimated costs ($0.05-0.20+)
- PR continuation estimates based on comment complexity
- Different costs for Python vs Rust (due to different toolchain context)
- Clear error message when no API key available
- User can cancel execution after seeing cost estimate
- Cost estimation includes complexity analysis and cost reduction tips

### 3.3 Container Execution (10 minutes)
**Setup:**
```bash
# Create simple test specification
cat > test_spec.md << 'EOF'
# Test Task
Create a simple "Hello World" Python script named hello.py that prints "Hello from Claude Agent!"
EOF
```

**Tests:**
- [ ] **Direct execution**: `python3 claude_agent.py run --base-image python:3.9 --spec test_spec.md --branch test/hello-world`
- [ ] **Container logs**: Check container executed without errors
- [ ] **Output verification**: Check if `hello.py` was created and works

**Expected Results:**
- Container executes successfully
- Files created in repository
- Git operations work correctly

### 3.4 Background Job Testing (5 minutes)
**Tests:**
- [ ] **Start daemon job (spec)**: `python3 claude_agent.py run --base-image python:3.9 --spec test_spec.md --branch test/daemon-job`
- [ ] **Start daemon job (PR)**: `python3 claude_agent.py run --base-image python:3.9 --pr $PR_NUMBER` 
- [ ] **Check job status**: `python3 claude_agent.py status`
- [ ] **View job logs**: `python3 claude_agent.py logs --job-id [ID]`
- [ ] **PR vs Issue job comparison**: Compare job data structures

**Expected Results:**
- Both spec and PR jobs start successfully
- Status tracking works for both modes
- PR jobs show different branch handling
- Logs accessible for both job types

---

## Phase 4: Cost Tracking & Advanced Features (40 minutes)

### 4.1 Cost Monitoring (15 minutes)
**Tests:**
- [ ] **Cost tracking execution**: Run a job and verify cost data is captured
- [ ] **Cost in new PR**: Verify cost information appears in new PR descriptions  
- [ ] **Cost in PR comments**: Verify cost appears in PR continuation comments
- [ ] **Job cost display**: `python3 claude_agent.py status` shows cost information

**Expected Results:**
- Cost data captured and stored
- Cost information in both new PRs and PR comments
- Cost visible in job status
- PR continuation shows cost of additional work

### 4.2 Language-Specific Features (25 minutes)
**Setup:**
```bash
# Create Rust test specification
cat > rust_test_spec.md << 'EOF'
# Rust Test Task
Create a simple "Hello World" Rust application with proper Cargo.toml
EOF
```

**Tests:**
- [ ] **Rust workflow**: `python3 claude_agent.py run --base-image rust:1.70 --spec rust_test_spec.md --branch test/rust-hello --language rust`
- [ ] **Rust PR continuation**: Create Rust PR, add @claude comment, test continuation
- [ ] **Security tools**: Verify Rust-specific tools available per language
- [ ] **Python vs Rust prompts**: Compare container prompts for different languages
- [ ] **Language-specific costs**: Compare costs between Python and Rust workflows

**Expected Results:**
- Language-specific toolchains work for both new work and PR continuation
- Security tools available per language (Python: bandit/safety, Rust: cargo-audit/clippy)
- Optimized prompts show correct tools for each language
- Cost tracking works across all languages

---

## Phase 5: End-to-End Integration (45 minutes)

### 5.1 Complete New Issue Workflow (15 minutes)
**Setup:**
```bash
# Create realistic test issue and specification
cat > integration_spec.md << 'EOF'
# Integration Test Task
Fix the authentication bug in the user login system:
1. Add proper error handling for invalid credentials
2. Add logging for failed login attempts  
3. Update unit tests
EOF
```

**Tests:**
- [ ] **Full issue workflow**: `python3 claude_agent.py run --base-image python:3.9 --spec integration_spec.md --branch fix/auth-bug --issue 1`
- [ ] **Verify PR creation**: Check PR has proper description, co-author, cost info
- [ ] **Code quality**: Review generated code for reasonableness

**Expected Results:**
- Complete workflow executes
- PR created with all features (co-author, cost, issue linking)
- Code changes are reasonable

### 5.2 NEW: Complete PR Continuation Workflow (20 minutes)
**Setup:**
```bash
# Use existing test PR and add comprehensive @claude feedback
gh pr comment $PR_NUMBER --body "@claude the error handling looks good, but please also add:
1. Input validation for email format
2. Rate limiting for failed login attempts  
3. Audit logging for security events
4. Unit tests for all new functionality

Please make these changes and let me know when ready for final review."
```

**Tests:**
- [ ] **Full PR continuation**: `python3 claude_agent.py run --base-image python:3.9 --pr $PR_NUMBER`
- [ ] **Multiple requests handling**: Verify all 4 requested changes are addressed
- [ ] **Progress tracking**: Check progress updates posted as PR comments
- [ ] **Final state**: Verify PR is updated (not new PR created)
- [ ] **Co-author preservation**: Check commits maintain co-author attribution
- [ ] **Cost tracking**: Verify cost information included in final PR comment

**Expected Results:**
- All requested changes implemented
- Progress updates posted as PR comments (not issue comments)
- Existing PR updated with additional commits
- Co-author attribution maintained
- Cost information shows cumulative work cost
- No new PR created

### 5.3 Cleanup and Validation (10 minutes)
**Tests:**
- [ ] **Job cleanup**: `python3 claude_agent.py cleanup --all`
- [ ] **Docker cleanup**: Verify containers removed
- [ ] **Repository state**: Check git state is clean
- [ ] **Cost summary**: Review total costs for testing
- [ ] **PR state verification**: Ensure test PRs are in expected final state

**Expected Results:**
- All jobs cleaned up successfully
- No orphaned containers
- Repository in good state
- Cost tracking worked throughout
- Test PRs properly updated (not duplicated)

---

## Quick Validation Checklist

After each phase, verify:
- [ ] No Python exceptions or crashes
- [ ] GitHub API calls work correctly  
- [ ] Docker containers start and stop properly
- [ ] Files are created in expected locations
- [ ] Git operations work correctly
- [ ] Cost tracking captures data
- [ ] Security tools are available
- [ ] **NEW**: PR continuation vs new PR creation logic works correctly
- [ ] **NEW**: @claude comment filtering works
- [ ] **NEW**: Co-author attribution maintained in all modes
- [ ] Cleanup functions work

---

## NEW: PR Continuation Specific Tests

Quick validation for PR features:
- [ ] **Comment filtering**: Only @claude mentions processed
- [ ] **Branch reuse**: Existing PR branch used, not new branch created
- [ ] **Context preservation**: PR description included in task context
- [ ] **Progress routing**: Updates go to PR comments, not issue comments  
- [ ] **Cost attribution**: Cost includes only new work, not original PR work
- [ ] **Co-author consistency**: All commits have co-author attribution

---

## Time Estimates:
- **Phase 1**: 50 minutes (GitHub features + PR comments)
- **Phase 2**: 45 minutes (PR continuation workflow)  
- **Phase 3**: 40 minutes (Docker/containers + PR jobs)
- **Phase 4**: 35 minutes (Cost tracking + languages)
- **Phase 5**: 50 minutes (End-to-end + PR workflows)
- **Setup/Buffer**: 15 minutes

**Total: ~3.5 hours**

---

## Troubleshooting Quick Fixes:
- **Docker issues**: `docker system prune -f`
- **GitHub auth**: `gh auth login`
- **Permission issues**: Check file permissions and API keys
- **Network timeouts**: Increase timeout values in code
- **Cost tracking**: Verify `/tmp/cost_data/` directories exist

---

## Success Criteria:
✅ All GitHub utilities work correctly  
✅ Docker containers execute successfully  
✅ PRs created with proper formatting and co-authors  
✅ **NEW**: PR continuation workflow works (comments → tasks → updates)
✅ **NEW**: @claude comment filtering and processing works
✅ Cost tracking captures and displays data  
✅ **NEW**: Cost estimation feature provides accurate estimates
✅ Language-specific features work (Python + Rust)  
✅ End-to-end workflow completes without manual intervention  
✅ **NEW**: Both new PR creation and PR continuation work seamlessly
✅ Cleanup functions work properly  

This testing plan validates all major features including the new PR continuation capability while staying within the 3.5-hour time budget.