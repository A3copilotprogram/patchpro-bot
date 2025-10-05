# GitHub Copilot Instructions for PatchPro Development

## Issue-Driven Development Workflow

### Philosophy

Every meaningful change to PatchPro should be tracked through a GitHub issue. This ensures:
- **Visibility**: Team knows what's being worked on
- **Context**: Future developers understand why changes were made
- **Traceability**: Commits link to discussions and decisions
- **Planning**: Work can be estimated and prioritized

### When to Create Issues

Create a GitHub issue BEFORE starting work on:

- ✅ New features or enhancements
- ✅ Significant bug fixes (not typos/quick fixes)
- ✅ Work spanning multiple files or components
- ✅ Architectural changes or refactoring
- ✅ Any work that takes >30 minutes
- ✅ Work that other team members should know about
- ✅ Performance improvements
- ✅ Security fixes

DO NOT create issues for:
- ❌ Typo fixes in comments
- ❌ Formatting/linting auto-fixes
- ❌ Version bumps (unless breaking changes)
- ❌ Trivial documentation updates

### Issue Creation Process

**1. STOP and Draft**
- Before writing any code, draft the issue description
- Include problem statement, scope, tasks, and DoD
- Think through the technical approach

**2. Discuss**
- Share issue draft with user/team lead for approval
- Incorporate feedback
- Ensure alignment on scope and approach

**3. Create**
- Once approved, create the issue in GitHub
- Use the Sprint-0 template format
- Assign appropriate labels and milestone

**4. Reference**
- Include issue number in ALL commits
- Update PR description with issue
- Link related issues (depends on, blocks, related to)

## Issue Template (Sprint-0 Format)

```markdown
## S{sprint}-{component}-{number}: Brief Title

**Epic**: Sprint-{number} (Team {team})
**Component**: {AG|AN|CI|QA|UI|DX}
**Priority**: {High|Medium|Low}
**Blocked by**: {issue numbers or "None"}
**Blocks**: {issue numbers or "None"}

### Problem Statement

**Current behavior:**
[Describe what's happening now]

**Expected behavior:**
[Describe what should happen]

**Impact:**
[Why this matters - user impact, technical debt, blockers]

### Root Cause Analysis

[Technical explanation of why the problem occurs - optional for features]

### Scope

**In scope:**
- Item 1
- Item 2

**Out of scope:**
- Item 1
- Item 2

### Tasks

- [ ] Task 1 with specific action
- [ ] Task 2 with specific action
- [ ] Task 3 with specific action
- [ ] Write/update tests
- [ ] Update documentation

### Definition of Done

- [ ] All tasks completed
- [ ] Tests pass (unit + integration)
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] No regressions introduced
- [ ] Acceptance criteria met

### Technical Notes

**Files to modify:**
- `path/to/file.py` - what changes

**Implementation approach:**
[Code snippets, algorithms, design decisions]

**Dependencies:**
[External libraries, other PRs, etc.]

### Related Issues

- Depends on: #X
- Related to: #Y
- Blocks: #Z
```

## Component Codes

- **AN**: Analysis (findings, normalization, schema)
- **AG**: Agent (LLM, prompts, patch generation, fix application)
- **CI**: CI/CD (GitHub Actions, workflows, deployment)
- **QA**: Quality Assurance (tests, validation, evaluation)
- **UI**: User Interface (CLI, output formatting, UX)
- **DX**: Developer Experience (setup, docs, tooling)
- **SEC**: Security (vulnerabilities, access control)
- **PERF**: Performance (optimization, profiling)

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): brief description [S0-XX-##]

Longer description explaining the change in detail.
Why was this change necessary? What problem does it solve?

- Key change 1
- Key change 2
- Key change 3

Technical notes:
- Implementation detail
- Design decision rationale

Fixes #issue-number
Related: #other-issue
```

### Commit Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance (deps, config, build)
- `style`: Code style (formatting, missing semicolons, etc.)
- `ci`: CI/CD changes

### Commit Scope Examples

- `analyzer`: Findings analysis logic
- `agent`: LLM agent and prompts
- `cli`: Command-line interface
- `diff`: Diff generation
- `hooks`: Git hooks
- `ci`: GitHub Actions

## PR Update Process

When adding work to an existing PR:

1. **Create new issue** for the additional work
2. **Update PR description** to list all issues addressed
3. **Reference issue** in commit messages
4. **Keep PR focused** - if scope grows too large, split into separate PRs

### PR Description Format

```markdown
## Description

[Brief overview of changes]

## Related Issues

Fixes #42
Fixes #43
Related: #44

## Changes

- Feature/fix 1 description
- Feature/fix 2 description

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## Example Workflow

### Scenario: Fixing patch path normalization

```bash
# 1. User reports issue
User: "The patches have wrong paths and git apply fails"

# 2. Copilot drafts issue
Copilot: [Analyzes problem, drafts S0-AG-02 issue with full details]

# 3. User approves
User: "Looks good, create it"
Copilot: [Creates issue in GitHub, gets #42]

# 4. Copilot implements fix with issue reference
git add src/patchpro_bot/analyzer.py
git commit -m "fix(analyzer): normalize file paths in findings [S0-AG-02]

Add _normalize_path() helper to RuffNormalizer and SemgrepNormalizer
classes. Converts absolute file paths to relative paths from git root
when creating Location objects.

This ensures that downstream components (LLM, patch generator) receive
clean relative paths instead of absolute paths, preventing malformed
patches that fail git apply.

- Add _normalize_path() method using git rev-parse
- Update Location creation in both normalizers
- Handle edge cases (already relative, no git repo)

Technical notes:
- Path normalization happens at finding creation time
- Prevents LLM from seeing confusing absolute paths
- Ensures patches have correct relative paths for git apply

Fixes #42"

# 5. Update PR description
Copilot: [Adds issue to PR #11's "Related Issues" section]

# 6. Mark tasks complete as work progresses
Copilot: [Updates issue checklist, adds comments with progress]
```

## Development Best Practices

### Before Starting Work

- [ ] Check if issue exists for this work
- [ ] If not, STOP and create issue first
- [ ] Read issue completely and understand scope
- [ ] Check for related/blocking issues
- [ ] Ask questions if anything unclear

### While Working

- [ ] Commit frequently with clear messages
- [ ] Reference issue number in every commit
- [ ] Update issue checklist as tasks complete
- [ ] Document decisions in issue comments
- [ ] Keep scope focused on issue objectives

### Before Pushing

- [ ] All commits reference issue number
- [ ] PR description lists all related issues
- [ ] Issue checklist reflects actual progress
- [ ] Tests pass locally
- [ ] Code reviewed (self-review first)

### After PR Merged

- [ ] Issue automatically closes (via "Fixes #X")
- [ ] Verify issue shows as closed
- [ ] Check if any blocked issues can now proceed

## Issue Lifecycle

```
[Draft] → [Open] → [In Progress] → [In Review] → [Done] → [Closed]
   ↓         ↓           ↓              ↓           ↓         ↓
Draft    Create     First      PR         PR      Issue
issue    in GH      commit     opened     merged   closed
```

## Labels and Organization

### Standard Labels

- `sprint-0`, `sprint-1`, etc. - Sprint tracking
- `priority:high`, `priority:medium`, `priority:low` - Prioritization
- `component:agent`, `component:analysis`, etc. - Component tracking
- `type:bug`, `type:feature`, `type:refactor` - Work type
- `blocked` - Waiting on dependencies
- `good-first-issue` - Good for new contributors

### Milestones

- Use milestones for sprint planning
- Group related issues under sprint milestones
- Track progress toward sprint goals

## Tips for AI-Assisted Development

### For GitHub Copilot

1. **Always ask about existing issues** before suggesting code changes
2. **Draft issues proactively** when user describes a problem
3. **Reference context** from related issues in commit messages
4. **Keep issue updated** with progress and blockers
5. **Link related work** to maintain traceability

### For Developers

1. **Use issue templates** consistently
2. **Keep issues focused** - one problem per issue
3. **Update regularly** - reflect current state
4. **Close promptly** - don't leave zombie issues
5. **Reference liberally** - over-linking is better than under-linking

## Shell Environment Guidelines

### Fish Shell Compatibility

This project uses **Fish shell** as the default shell. All terminal commands must be Fish-compatible.

**Key Differences from Bash:**
- ❌ **No heredocs**: Fish doesn't support `<<EOF` syntax
- ❌ **Different logic**: Use `and`/`or` instead of `&&`/`||`
- ❌ **Different variables**: Use `set` instead of `export`

**CRITICAL: Always Use Scripts for Complex/Multi-line Commands**

**❌ NEVER do this in terminal directly:**
```fish
# WRONG - Complex command inline
gh issue create --title "..." --body "..." --label "..."
```

**✅ ALWAYS create a script file:**
```fish
# CORRECT - Create script first
create_file /tmp/script.sh "#!/bin/bash\ncommand..."
chmod +x /tmp/script.sh
/tmp/script.sh
```

**When to use scripts:**
- Any command > 80 characters
- Commands with multi-line arguments
- Commands with special characters (quotes, parentheses, etc.)
- GitHub CLI commands (gh issue, gh pr, etc.)
- Any command that would use heredocs in bash

**Use printf for Simple Inline Scripts:**

```fish
# ✅ For simple one-liners only
printf 'import json\nprint("test")\n' | python3
```

**Chain Commands:**

```fish
# ✅ CORRECT - Fish shell
command1; and command2

# ❌ WRONG - Bash syntax
command1 && command2
```

### For GitHub Copilot

When generating terminal commands:
1. **Always use Fish shell syntax**
2. **Use temp files** (`/tmp/*.py`, `/tmp/*.sh`) for multi-line scripts
3. **Test commands** are Fish-compatible before suggesting
4. **Avoid heredocs** - use `cat > file` instead
5. **Use `;` or `; and`** for command chaining, not `&&`

## Questions?

If unclear about:
- Whether to create an issue → Create it (better to over-document)
- How to scope an issue → Ask team lead
- How to reference issues → Follow examples in this doc
- Issue numbering → Follow S{sprint}-{component}-{number} format
- Shell syntax → Use Fish shell, not Bash

---

**Last Updated**: 2025-10-05  
**Maintained By**: Team PLG_5  
**Questions**: Ask in #patchpro-dev channel
