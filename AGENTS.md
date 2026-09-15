# RolePointer Agent Rules & Execution Guidelines

This repository follows the autonomous execution guidelines defined in [rule.md](file:///f:/Hackathons/Agents%20for%20Humans/AntigravityBuild/EverydayAgents/rolepointer/rule.md).

## Core Principles

1. **Autonomous Execution After Plan Approval**: Once planning is complete or a `/goal` session begins, execute all code edits, automated test runs (`uv run pytest`), self-healing debugging loops, and `git commit` operations sequentially without pausing for intermediate confirmation.
2. **Deterministic Verification**: Never assume tests pass; execute test suites and verify exit codes before committing.
3. **Automated Git Commits**: Create conventional git commits (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`) automatically when tasks/milestones pass verification.
4. **Self-Healing**: Diagnose and resolve errors, test failures, or syntax issues autonomously without stalling.
