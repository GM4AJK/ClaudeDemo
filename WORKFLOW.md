# Demo Workflow

This file defines the standard step-by-step process for implementing each requirement
during the live demo. Follow every step in order.

---

## For each requirement

### 1. Create the requirements doc

```
Docs/requirements/N-slug/README.md
```

Write the README covering: goal, test setup, measurement method, theory, and acceptance
criteria. This is the specification — write it before any code.

### 2. Commit and push the doc

```bash
git add Docs/requirements/N-slug/README.md
git commit -m "Add Req N requirements doc: <short description>"
git push
```

### 3. Create a GitHub issue

```bash
gh issue create --title "Req N: <title>" --body "Spec: Docs/requirements/N-slug/README.md"
```

Note the issue number.

### 4. Create a feature branch

```bash
git checkout -b feature/N-slug
```

### 5. Implement firmware changes

- Edit `Core/Src/main.c` and/or `Core/Src/stm32g4xx_it.c` inside
  `USER CODE BEGIN` / `USER CODE END` blocks
- Peripheral init in static functions called from `USER CODE BEGIN 2`
- Bare-metal register writes only — no HAL peripheral APIs

### 6. Write the verification script

Place the script alongside the README:

```
Docs/requirements/N-slug/test_<name>.py
```

### 7. Commit and push the implementation

```bash
git add Core/Src/main.c Core/Src/stm32g4xx_it.c \
        Docs/requirements/N-slug/test_<name>.py
git commit -m "Implement Req N: <short description>"
git push -u origin feature/N-slug
```

### 8. Open a pull request

```bash
gh pr create --title "Req N: <title>" \
             --body "Implements #<issue number> ..."
```

### 9. User builds and tests on hardware

The user builds in STM32CubeIDE and runs the verification script. Claude does not build
or flash — the user does this.

> **► Run:** `python3 Docs/requirements/N-slug/test_<name>.py`

### 10. Merge on pass

Once the script passes:

```bash
gh pr merge <PR number> --squash --delete-branch
git checkout main
git pull
```

---

## Commit conventions

- No GPG signing required — commit directly
- Always append to commit message body:
  ```
  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  ```
- Use a heredoc for multi-line messages to preserve formatting

## Git remote

SSH: `git@github.com:GM4AJK/ClaudeDemo.git`
The `gh` CLI is authenticated and can create issues and PRs directly.
