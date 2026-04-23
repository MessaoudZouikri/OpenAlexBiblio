---
name: Git workflow — no commits or pushes
description: User handles all git commits and pushes; Claude must never commit or push
type: feedback
---
Never commit or push to GitHub. Leave all git commits and pushes to the user.

**Why:** The CI pipeline (GitHub Actions) gates merges on ruff/lint checks. The user wants to review and commit themselves rather than having Claude make commits autonomously.

**How to apply:** Fix code issues and leave the files modified but never run `git commit` or `git push`. When done, report what was changed and let the user commit.
