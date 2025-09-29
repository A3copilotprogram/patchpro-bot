# PatchPro-Bot Automation Script
# Usage: .\dev.ps1 [test|lint|semgrep|all]

param(
    [string]$Task = "all"
)

function Run-Test {
    Write-Host "Running tests..."
    $env:PYTHONPATH = "src"
    pytest tests
}

function Run-Lint {
    Write-Host "Running Ruff linter..."
    ruff src/patchpro_bot
}

function Run-Semgrep {
    Write-Host "Running Semgrep..."
    semgrep --config=semgrep.yml src/patchpro_bot
}

switch ($Task) {
    "test"    { Run-Test }
    "lint"    { Run-Lint }
    "semgrep" { Run-Semgrep }
    "all"     { Run-Lint; Run-Semgrep; Run-Test }
    default   { Write-Host "Unknown task: $Task"; exit 1 }
}
