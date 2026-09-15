# Autonomous Execution & Pipeline Rules (`rule.md`)

## 1. Core Principle: Zero-Friction Autonomous Execution

Once an implementation plan is approved by the user, or when a task is initiated (especially with `/goal`), **DO NOT pause to ask for permission for routine implementation, testing, debugging, or git operations**. Proceed autonomously through the entire lifecycle until the goal is fully accomplished.

---

## 2. Autonomous Execution Lifecycle

Execute tasks in the following unbroken sequence:

```
[Plan Approved / Goal Started]
               │
               ▼
   1. Implement Source Code / Edits
               │
               ▼
   2. Run Automated Tests & Linters
         (`uv run pytest`)
               │
      ┌────────┴────────┐
   [Pass]            [Fail]
      │                 │
      │        3. Self-Diagnose & Fix
      │        (Loop autonomously to 2)
      ▼
   4. Git Stage & Commit (`git commit -m "..."`)
               │
               ▼
   5. Final Verification & Walkthrough Artifact
```

### Step 1: Implementation
- Create or modify all necessary files directly.
- Ensure type annotations, docstrings, and project conventions are strictly followed.

### Step 2: Automated Verification
- Run the test suite immediately after code changes:
  ```bash
  uv run pytest tests/
  ```
- Test specific modules if doing targeted work, but always run full relevant suite before committing.

### Step 3: Autonomous Self-Healing & Debugging
- If any test or command fails:
  - **Do NOT ask the user what to do**.
  - Inspect tracebacks and logs autonomously.
  - Apply the code fix.
  - Re-run the tests until 100% green.

### Step 4: Automated Git Commits
- After tests pass, immediately stage and commit changes without prompting for approval:
  ```bash
  git add <modified/created files>
  git commit -m "<type>(<scope>): <clear descriptive message>"
  ```
- Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).

### Step 5: Completion & Deliverables
- Update the walkthrough artifact (`walkthrough.md`) with:
  - Changes made across files
  - Test outcomes and verification logs
  - Commit SHA / status

---

## 3. Decision Matrix: When to Proceed vs. When to Pause

| Scenario | Action |
| :--- | :--- |
| Editing source files, tests, or config | **Proceed autonomously** |
| Running `pytest`, `uv`, `ruff`, or local scripts | **Proceed autonomously** |
| Fixing build, syntax, or test failures | **Proceed autonomously** |
| Staging files and creating git commits | **Proceed autonomously** |
| Long-running multi-file feature implementations | **Proceed autonomously** |
| Missing API keys or secrets required to test live external services | **Pause and ask user** |
| Irreversible destructive actions outside the workspace | **Pause and ask user** |
| Fundamental requirement conflict requiring strategic product pivot | **Pause and ask user** |

---

## 4. Best Practices for `/goal` Mode

When operating under `/goal`:
1. **Relentless Completion**: Do not stop at the first milestone; continue through all sub-tasks until the high-level objective is completely met and verified.
2. **Deterministic Verification**: Verify code with actual command execution, not assumptions.
3. **Clean Working Tree**: Leave the repository in a clean, working, tested, and committed state.
