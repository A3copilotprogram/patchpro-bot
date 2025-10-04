# Contributing to PatchPro

Thank you for your interest in contributing to PatchPro! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Issue-Driven Development](#issue-driven-development)
- [Setting Up Development Environment](#setting-up-development-environment)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Code Style](#code-style)

## Development Workflow

PatchPro follows an **issue-driven development** workflow. All significant work should be tracked through GitHub issues before code is written.

### Quick Start

1. **Find or create an issue** for the work you want to do
2. **Assign yourself** to the issue
3. **Create a branch** from `agent-dev` (or appropriate base branch)
4. **Make changes** with frequent commits referencing the issue
5. **Test thoroughly** - run tests and manual validation
6. **Submit a PR** linking to the issue
7. **Address review feedback**
8. **Merge** when approved

## Issue-Driven Development

### When to Create an Issue

Create an issue BEFORE starting work on:

- ✅ New features or enhancements
- ✅ Bug fixes that aren't trivial (> 5 minutes)
- ✅ Work spanning multiple files
- ✅ Architectural changes
- ✅ Performance improvements
- ✅ Security fixes

See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) for complete guidelines.

### Issue Naming Convention

Format: `S{sprint}-{component}-{number}: Brief Title`

**Components:**
- **AN**: Analysis (findings, normalization)
- **AG**: Agent (LLM, patches, fixes)
- **CI**: CI/CD (workflows, automation)
- **QA**: Quality Assurance (tests, validation)
- **UI**: User Interface (CLI, output)
- **DX**: Developer Experience (docs, tooling)

**Example:** `S0-AG-02: Fix Patch Path Normalization for LLM-Generated Diffs`

### Issue Template

Use the Sprint-0 template format with:
- Problem statement (current vs expected behavior)
- Root cause analysis (if applicable)
- Scope definition
- Task checklist
- Definition of Done
- Technical notes
- Related issues

See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) for the full template.

## Setting Up Development Environment

### Prerequisites

- Python 3.11+ or 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git
- OpenAI API key (for LLM features)

### Installation

```bash
# Clone the repository
git clone https://github.com/A3copilotprogram/patchpro-bot.git
cd patchpro-bot

# Create virtual environment
uv venv  # or: python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install in editable mode with dependencies
uv pip install -e .  # or: pip install -e .

# Set up environment variables
cp .env.example .env  # if it exists
# Edit .env and add your OPENAI_API_KEY
```

### Initialize Git Hooks (Optional but Recommended)

```bash
# Install git hooks for local development workflow
patchpro init --hooks
```

This installs:
- **Post-commit hook**: Runs background analysis after each commit
- **Pre-push hook**: Shows findings and prompts for action before push

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/S0-AG-02-fix-patch-paths`
- `fix/S0-AN-03-normalize-findings`
- `docs/update-contributing-guide`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): brief description [S0-XX-##]

Longer explanation of the change (optional but encouraged).
Include why the change was needed and how it solves the problem.

- Key change 1
- Key change 2

Fixes #issue-number
```

**Commit types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Test updates
- `chore`: Maintenance
- `ci`: CI/CD changes

**Example:**

```bash
git commit -m "fix(analyzer): normalize file paths in findings [S0-AG-02]

Add _normalize_path() helper to RuffNormalizer and SemgrepNormalizer.
Converts absolute paths to relative paths from git root when creating
Location objects.

- Add _normalize_path() using git rev-parse
- Update Location creation in normalizers
- Handle edge cases (relative paths, no git repo)

Fixes #42"
```

### Referencing Issues

**Always reference issues in:**
- Commit messages (include issue number in brackets)
- PR descriptions (use "Fixes #X" or "Related: #Y")
- Code comments (when explaining why something exists)

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_analyzer.py

# Run with coverage
pytest --cov=patchpro_bot --cov-report=html

# Run integration tests
pytest tests/integration/
```

### Writing Tests

- Write tests for all new features
- Ensure tests pass before submitting PR
- Aim for >80% code coverage
- Include both unit and integration tests where applicable

### Manual Testing

For changes affecting the workflow:

```bash
# Test analysis locally
patchpro analyze

# Test git hooks
git commit -m "test commit"  # Should trigger post-commit hook
git push origin branch-name  # Should trigger pre-push hook

# Test patch generation
patchpro review-findings --auto-amend
```

## Submitting Pull Requests

### PR Checklist

Before submitting:

- [ ] All commits reference issue numbers
- [ ] Tests pass locally
- [ ] Code follows style guidelines (see below)
- [ ] Documentation updated (if needed)
- [ ] PR description includes:
  - Summary of changes
  - Related issues (Fixes #X)
  - Testing performed
  - Screenshots (if UI changes)

### PR Description Template

```markdown
## Description

[Brief summary of what this PR does]

## Related Issues

Fixes #42
Related: #43

## Changes

- Change 1 with explanation
- Change 2 with explanation

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Tested with git hooks workflow

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] All conversations resolved
```

### Review Process

1. **Self-review first** - read your own code and comments
2. **Address CI failures** - fix any automated test failures
3. **Respond to feedback** - engage with reviewers constructively
4. **Make requested changes** - commit with clear messages
5. **Request re-review** - once changes are made

## Code Style

### Python Style

Follow [PEP 8](https://pep8.org/) with these specifics:

- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes for strings
- **Imports**: Organized by standard lib, third-party, local
- **Type hints**: Use for function signatures
- **Docstrings**: Google style for functions and classes

### Formatting

We use automated formatters:

```bash
# Format code with Black
black src/ tests/

# Sort imports
isort src/ tests/

# Lint with ruff
ruff check src/ tests/
```

### Documentation Style

- **Clear and concise** - explain WHY not just WHAT
- **Code examples** - include for complex features
- **Diagrams** - use Mermaid for architecture/flow diagrams
- **Keep updated** - docs should match current code

## Git Hooks Workflow (Local Development)

PatchPro has a local development workflow enabled by git hooks:

1. **Make changes** to your code
2. **Commit** (`git commit -m "..."`)
   - Post-commit hook runs analysis in background
   - You continue working immediately (non-blocking)
3. **Continue working** while analysis runs
4. **Push when ready** (`git push`)
   - Pre-push hook shows findings from background analysis
   - Choose action: `fix` (apply patches), `push` (ignore), or `cancel`
5. **Review and fix** findings before they reach the remote

### Hook Commands

```bash
# Check analysis status
patchpro check-status

# Review findings manually
patchpro review-findings

# Manually trigger analysis
patchpro analyze-commit
```

## Getting Help

- **Documentation**: Check [`docs/`](docs/) folder
- **Issues**: Search existing issues or create new one
- **Discussions**: Use GitHub Discussions for questions
- **Copilot Instructions**: See [`.github/copilot-instructions.md`](.github/copilot-instructions.md)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

---

**Thank you for contributing to PatchPro!** 🎉
