# PatchPro-Bot Automation Makefile

.PHONY: test lint semgrep all

# Run tests with correct PYTHONPATH

test:
	@echo Running tests...
	PYTHONPATH=src pytest tests

# Run Ruff linter
lint:
	@echo Running Ruff linter...
	ruff src/patchpro_bot

# Run Semgrep static analysis
semgrep:
	@echo Running Semgrep...
	semgrep --config=semgrep.yml src/patchpro_bot

# Run all checks
all: lint semgrep test
	@echo All checks passed!
