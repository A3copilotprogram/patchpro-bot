# PatchPro — Pod-Level Requirements (Sprint-0)

This document breaks down requirements for each pod to support our **Sprint-0 goal**: a *comment-only vertical slice* on demo PRs. Each pod should fill in its section with specific requirements, actions, and outputs.

---

## 1. Agent Core

*Scope: Prompt scaffolding & guardrails for generating minimal diffs.*

**Requirements:**

* Define the **prompt format** (inputs, expected output style, minimal diff block).
* Add **guardrails**:

  * Max number of lines changed.
  * Handle large files gracefully.
  * Fallback behavior if LLM output is empty or invalid.
* CLI entrypoint: `patchpro agent run --inputs <findings.json> --out patchpro.md`.
* Output spec: structured markdown snippet for sticky PR comment.

---

## 2. Analyzer/Rules

*Scope: Normalizing static analysis findings (Ruff, Semgrep).*

**Requirements:**

* Pin versions of Ruff and Semgrep.
* Define **config baseline** (e.g. `.ruff.toml`, `semgrep.yml`).
* Ensure findings exported as **JSON** with consistent schema.
* Write schema: `schemas/findings.v1.json`.
* Normalize: deduplicate, unify file\:line format, add severity labels.

---

## 3. CI/DevEx

*Scope: GitHub Actions workflow orchestration.*

**Requirements:**

* Create workflow `patchpro.yml` triggered on `pull_request`.
* Steps:

  1. Checkout repo.
  2. Run Ruff & Semgrep → export artifacts.
  3. Run PatchPro agent → generate `patchpro.md`.
  4. Post sticky PR comment with `patchpro.md`.
* Permissions: minimal (`contents: read`, `pull-requests: write`).
* Concurrency: ensure only 1 workflow per PR runs at a time.
* Timeout: ≤ 5 min per job.

---

## 4. Eval/QA

*Scope: Golden PRs and evaluation rubric.*

**Requirements:**

* Create **3–5 golden PRs** in `patchpro-demo-repo` (common lint/fix cases).
* Document **expected PatchPro comment** for each.
* Define rubric (LLM-as-judge or human):

  * Did PatchPro detect the issue?
  * Did it propose the correct minimal diff?
  * Was the comment structured and clear?
* Track pass/fail results per golden PR.

---

## 5. UI (Optional)

*Scope: Playground for manual prompt/diff testing.*

**Requirements:**

* Minimal web/CLI playground to test prompts locally.
* Input: sample findings JSON.
* Output: markdown preview of suggested comment.
* Keep styling consistent with CI sticky comment.

---

## Next Steps

* Each pod to fill in their section by **\[set date, e.g. Wed, Sept 3]**.
* Once filled, we’ll open GitHub issues/branches mapped to these requirements.
* Eval/QA will then test the first end-to-end vertical slice using golden PRs.

---

⚖️ This doc bridges **high-level flow → actionable tasks**. When filled, it becomes our shared reference for Sprint-0.

