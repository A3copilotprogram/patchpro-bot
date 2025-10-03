"""
CLI interface for PatchPro with analyzer functionality and LLM integration.
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .analyzer import FindingsAnalyzer, NormalizedFindings
from .agent_core import AgentCore, AgentConfig

app = typer.Typer(
    name="patchpro",
    help="PatchPro: CI code-repair assistant with LLM integration",
    add_completion=False,
)

console = Console()


@app.command()
def analyze(
    paths: List[str] = typer.Argument(..., help="Files or directories to analyze"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for normalized findings"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json, table)"),
    ruff_config: Optional[str] = typer.Option(None, "--ruff-config", help="Path to Ruff configuration file"),
    semgrep_config: Optional[str] = typer.Option(None, "--semgrep-config", help="Path to Semgrep configuration file"),
    tools: List[str] = typer.Option(["ruff", "semgrep"], "--tools", "-t", help="Tools to run (ruff, semgrep)"),
    artifacts_dir: str = typer.Option("artifact/analysis", "--artifacts-dir", "-a", help="Directory to store raw analysis artifacts"),
) -> None:
    """Run static analysis and normalize findings."""
    
    console.print("[bold blue]🔍 Running PatchPro Analysis...[/bold blue]")
    
    # Create artifacts directory
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    
    # Run tools and collect outputs
    tool_outputs = {}
    
    if "ruff" in tools:
        console.print("Running Ruff analysis...")
        ruff_output = _run_ruff(paths, ruff_config, artifacts_path)
        if ruff_output:
            tool_outputs["ruff"] = ruff_output
    
    if "semgrep" in tools:
        console.print("Running Semgrep analysis...")
        semgrep_output = _run_semgrep(paths, semgrep_config, artifacts_path)
        if semgrep_output:
            tool_outputs["semgrep"] = semgrep_output
    
    if not tool_outputs:
        console.print("[yellow]⚠️  No analysis results found.[/yellow]")
        return
    
    # Normalize findings
    console.print("Normalizing findings...")
    analyzer = FindingsAnalyzer()
    normalized_results = analyzer.normalize_findings(tool_outputs)
    
    if len(normalized_results) > 1:
        merged_findings = analyzer.merge_findings(normalized_results)
    else:
        merged_findings = normalized_results[0] if normalized_results else NormalizedFindings([], None)
    
    # Output results
    if format == "json":
        if output:
            merged_findings.save(output)
            console.print(f"[green]✅ Results saved to {output}[/green]")
        else:
            console.print(merged_findings.to_json())
    elif format == "table":
        _display_findings_table(merged_findings)
    
    # Summary
    total_findings = len(merged_findings.findings)
    console.print(f"\n[bold green]📊 Analysis Complete: {total_findings} finding(s)[/bold green]")


@app.command()
def normalize(
    analysis_dir: str = typer.Argument(..., help="Directory containing analysis results"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for normalized findings"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json, table)"),
) -> None:
    """Normalize existing analysis results."""
    
    console.print(f"[bold blue]🔄 Normalizing findings from {analysis_dir}...[/bold blue]")
    
    analyzer = FindingsAnalyzer()
    
    try:
        normalized_findings = analyzer.load_and_normalize(analysis_dir)
        
        if format == "json":
            if output:
                normalized_findings.save(output)
                console.print(f"[green]✅ Results saved to {output}[/green]")
            else:
                console.print(normalized_findings.to_json())
        elif format == "table":
            _display_findings_table(normalized_findings)
        
        total_findings = len(normalized_findings.findings)
        console.print(f"\n[bold green]📊 Normalization Complete: {total_findings} finding(s)[/bold green]")
        
    except Exception as e:
        console.print(f"[red]❌ Error normalizing findings: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run_ci(
    artifacts_dir: str = typer.Option("artifact", "--artifacts", "-a", help="Artifacts directory"),
    base_dir: Optional[str] = typer.Option(None, "--base-dir", help="Base directory for analysis"),
    tools: List[str] = typer.Option(["ruff", "semgrep"], "--tools", "-t", help="Tools to run"),
    ruff_config: Optional[str] = typer.Option(None, "--ruff-config", help="Path to Ruff configuration file"),
    semgrep_config: Optional[str] = typer.Option(None, "--semgrep-config", help="Path to Semgrep configuration file"),
) -> None:
    """Run complete CI pipeline with LLM integration."""
    
    console.print("[bold blue]🚀 Running PatchPro CI Pipeline...[/bold blue]")
    
    try:
        # Setup paths
        artifacts_path = Path(artifacts_dir)
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        base_path = Path(base_dir) if base_dir else Path.cwd()
        analysis_path = artifacts_path / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Run analysis and normalization
        console.print("[bold cyan]🔍 Running analysis and normalization...[/bold cyan]")
        
        # Run tools and collect outputs
        tool_outputs = {}
        
        if "ruff" in tools:
            console.print("Running Ruff analysis...")
            ruff_output = _run_ruff([str(base_path)], ruff_config, analysis_path)
            if ruff_output:
                tool_outputs["ruff"] = ruff_output
        
        if "semgrep" in tools:
            console.print("Running Semgrep analysis...")
            semgrep_output = _run_semgrep([str(base_path)], semgrep_config, analysis_path)
            if semgrep_output:
                tool_outputs["semgrep"] = semgrep_output
        
        # Normalize findings
        console.print("Normalizing findings...")
        analyzer = FindingsAnalyzer()
        normalized_results = analyzer.normalize_findings(tool_outputs)
        normalized_findings = analyzer.merge_findings(normalized_results)
        
        # Save normalized findings
        normalized_findings.save(str(analysis_path / "normalized_findings.json"))
        console.print(f"[green]✅ Analysis complete: {len(normalized_findings.findings)} findings[/green]")
        
        # Step 2: Run LLM pipeline
        console.print("[bold cyan]🤖 Running LLM pipeline...[/bold cyan]")
        config = AgentConfig(
            analysis_dir=analysis_path,
            artifact_dir=artifacts_path,
            base_dir=base_path,
        )
        
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        
        console.print(f"[green]✅ CI Pipeline Complete: {results}[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ CI Pipeline failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate_schema(
    findings_file: str = typer.Argument(..., help="Path to findings JSON file"),
) -> None:
    """Validate findings file against schema."""
    
    console.print(f"[bold blue]✅ Validating {findings_file}...[/bold blue]")
    
    try:
        # Load findings
        findings_path = Path(findings_file)
        if not findings_path.exists():
            console.print(f"[red]❌ File not found: {findings_file}[/red]")
            raise typer.Exit(1)
        
        findings_data = json.loads(findings_path.read_text())
        
        # Basic validation (could be enhanced with jsonschema library)
        required_keys = ["findings", "metadata"]
        for key in required_keys:
            if key not in findings_data:
                console.print(f"[red]❌ Missing required key: {key}[/red]")
                raise typer.Exit(1)
        
        # Check findings structure
        if not isinstance(findings_data["findings"], list):
            console.print("[red]❌ 'findings' must be a list[/red]")
            raise typer.Exit(1)
        
        # Check metadata structure
        metadata = findings_data["metadata"]
        required_metadata = ["tool", "version", "total_findings"]
        for key in required_metadata:
            if key not in metadata:
                console.print(f"[red]❌ Missing metadata key: {key}[/red]")
                raise typer.Exit(1)
        
        console.print(f"[green]✅ Schema validation passed! Found {len(findings_data['findings'])} findings[/green]")
        
    except json.JSONDecodeError:
        console.print(f"[red]❌ Invalid JSON in {findings_file}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Validation error: {e}[/red]")
        raise typer.Exit(1)


def _run_ruff(paths: List[str], config: Optional[str], artifacts_dir: Path) -> Optional[List]:
    """Run Ruff and return JSON output."""
    try:
        # Try to find ruff executable
        import shutil
        ruff_cmd = shutil.which("ruff")
        if not ruff_cmd:
            # Try in venv on Windows
            venv_ruff = Path(sys.executable).parent / "ruff.exe"
            if venv_ruff.exists():
                ruff_cmd = str(venv_ruff)
        
        if not ruff_cmd:
            raise FileNotFoundError("ruff not found")
        
        cmd = [ruff_cmd, "check", "--output-format=json"]
        
        if config:
            cmd.extend(["--config", config])
        
        cmd.extend(paths)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Ruff returns non-zero when issues found
        )
        
        if result.stdout:
            output = json.loads(result.stdout)
            # Save raw output
            (artifacts_dir / "ruff.json").write_text(result.stdout)
            return output
        
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]⚠️  Ruff execution failed: {e}[/yellow]")
    except json.JSONDecodeError:
        console.print("[yellow]⚠️  Failed to parse Ruff JSON output[/yellow]")
    except FileNotFoundError:
        console.print("[yellow]⚠️  Ruff not found. Install with: pip install ruff[/yellow]")
    
    return None


def _run_semgrep(paths: List[str], config: Optional[str], artifacts_dir: Path) -> Optional[dict]:
    """Run Semgrep and return JSON output."""
    try:
        # Try to find semgrep executable  
        import shutil
        semgrep_cmd = shutil.which("semgrep")
        if not semgrep_cmd:
            # Try in venv on Windows
            venv_semgrep = Path(sys.executable).parent / "semgrep"
            if venv_semgrep.exists():
                semgrep_cmd = str(venv_semgrep)
        
        if not semgrep_cmd:
            raise FileNotFoundError("semgrep not found")
        
        cmd = [semgrep_cmd, "--json", "--quiet"]
        
        if config:
            cmd.extend(["--config", config])
        else:
            # Use some basic rules if no config provided
            cmd.extend(["--config=auto"])
        
        cmd.extend(paths)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Semgrep returns non-zero when issues found
        )
        
        if result.stdout:
            output = json.loads(result.stdout)
            # Save raw output
            (artifacts_dir / "semgrep.json").write_text(result.stdout)
            return output
        
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]⚠️  Semgrep execution failed: {e}[/yellow]")
    except json.JSONDecodeError:
        console.print("[yellow]⚠️  Failed to parse Semgrep JSON output[/yellow]")
    except FileNotFoundError:
        console.print("[yellow]⚠️  Semgrep not found. Install with: pip install semgrep[/yellow]")
    
    return None


def _display_findings_table(findings: NormalizedFindings) -> None:
    """Display findings in a rich table format."""
    
    if not findings.findings:
        console.print("[yellow]No findings to display.[/yellow]")
        return
    
    # Create summary panel
    summary = Panel(
        f"Tool: {findings.metadata.tool}\n"
        f"Version: {findings.metadata.version}\n"
        f"Timestamp: {findings.metadata.timestamp}\n"
        f"Total Findings: {findings.metadata.total_findings}",
        title="Analysis Summary",
        border_style="blue"
    )
    console.print(summary)
    console.print()
    
    # Create findings table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Line", style="green", justify="right")
    table.add_column("Rule", style="yellow")
    table.add_column("Severity", style="red")
    table.add_column("Category", style="blue")
    table.add_column("Message", style="white")
    
    # Sort findings by file and line
    sorted_findings = sorted(
        findings.findings,
        key=lambda f: (f.location.file, f.location.line)
    )
    
    for finding in sorted_findings:
        # Truncate message if too long
        message = finding.message
        if len(message) > 80:
            message = message[:77] + "..."
        
        # Color code severity
        severity_style = {
            "error": "[red]ERROR[/red]",
            "warning": "[yellow]WARNING[/yellow]",
            "info": "[blue]INFO[/blue]",
            "note": "[dim]NOTE[/dim]"
        }.get(finding.severity, finding.severity)
        
        table.add_row(
            finding.location.file,
            str(finding.location.line),
            finding.rule_id,
            severity_style,
            finding.category.upper(),
            message
        )
    
    console.print(table)


@app.command()
def watch(
    paths: List[str] = typer.Argument(..., help="Paths to watch for changes"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (json, table)"),
    tools: List[str] = typer.Option(["ruff"], "--tools", "-t", help="Tools to run"),
    interval: int = typer.Option(2, "--interval", "-i", help="Watch interval in seconds"),
) -> None:
    """Watch files for changes and run analysis automatically."""
    import time
    import hashlib
    from pathlib import Path
    
    console.print(f"[bold blue]👀 Watching {len(paths)} path(s) for changes...[/bold blue]")
    console.print(f"Tools: {', '.join(tools)}")
    console.print("Press Ctrl+C to stop")
    
    # Track file hashes
    file_hashes = {}
    
    def get_file_hash(file_path):
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None
    
    def scan_files():
        python_files = []
        for path in paths:
            path_obj = Path(path)
            if path_obj.is_file() and path_obj.suffix == '.py':
                python_files.append(str(path_obj))
            elif path_obj.is_dir():
                python_files.extend([str(f) for f in path_obj.rglob('*.py')])
        return python_files
    
    try:
        while True:
            changed_files = []
            current_files = scan_files()
            
            for file_path in current_files:
                current_hash = get_file_hash(file_path)
                if current_hash and file_path in file_hashes:
                    if file_hashes[file_path] != current_hash:
                        changed_files.append(file_path)
                file_hashes[file_path] = current_hash
            
            if changed_files:
                console.print(f"\n[green]📝 Changes detected in {len(changed_files)} file(s)[/green]")
                for file in changed_files:
                    console.print(f"  • {file}")
                
                # Run analysis on changed files
                try:
                    analyzer = FindingsAnalyzer()
                    tool_outputs = {}
                    
                    if "ruff" in tools:
                        ruff_output = _run_ruff(changed_files, None, Path.cwd() / "artifacts")
                        if ruff_output:
                            tool_outputs["ruff"] = ruff_output
                    
                    if "semgrep" in tools:
                        semgrep_output = _run_semgrep(changed_files, None, Path.cwd() / "artifacts")
                        if semgrep_output:
                            tool_outputs["semgrep"] = semgrep_output
                    
                    if tool_outputs:
                        normalized_results = analyzer.normalize_findings(tool_outputs)
                        merged_findings = analyzer.merge_findings(normalized_results)
                        
                        if format == "table":
                            _display_findings_table(merged_findings)
                        else:
                            console.print(merged_findings.to_json())
                        
                        console.print(f"[green]✅ Found {len(merged_findings.findings)} findings[/green]")
                    else:
                        console.print("[green]✅ No issues found[/green]")
                        
                except Exception as e:
                    console.print(f"[red]❌ Analysis failed: {e}[/red]")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Watch mode stopped[/yellow]")


@app.command()
def diff_analyze(
    base: str = typer.Option("origin/main", "--base", "-b", help="Base branch/commit to compare against"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (json, table)"),
    tools: List[str] = typer.Option(["ruff"], "--tools", "-t", help="Tools to run"),
    staged_only: bool = typer.Option(False, "--staged", help="Analyze only staged changes"),
) -> None:
    """Analyze only changed lines compared to base branch."""
    import subprocess
    
    console.print(f"[bold blue]🔍 Analyzing changes against {base}...[/bold blue]")
    
    try:
        if staged_only:
            # Get staged files
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, check=True
            )
        else:
            # Get changed files since base
            result = subprocess.run(
                ["git", "diff", f"{base}...HEAD", "--name-only"],
                capture_output=True, text=True, check=True
            )
        
        changed_files = [f.strip() for f in result.stdout.split('\n') if f.strip().endswith('.py')]
        
        if not changed_files:
            console.print("[yellow]No Python files changed[/yellow]")
            return
        
        console.print(f"Analyzing {len(changed_files)} changed file(s):")
        for file in changed_files:
            console.print(f"  • {file}")
        
        # Run analysis
        analyzer = FindingsAnalyzer()
        tool_outputs = {}
        artifacts_dir = Path.cwd() / "artifacts"
        
        if "ruff" in tools:
            ruff_output = _run_ruff(changed_files, None, artifacts_dir)
            if ruff_output:
                tool_outputs["ruff"] = ruff_output
        
        if "semgrep" in tools:
            semgrep_output = _run_semgrep(changed_files, None, artifacts_dir)
            if semgrep_output:
                tool_outputs["semgrep"] = semgrep_output
        
        if tool_outputs:
            normalized_results = analyzer.normalize_findings(tool_outputs)
            merged_findings = analyzer.merge_findings(normalized_results)
            
            if format == "table":
                _display_findings_table(merged_findings)
            else:
                console.print(merged_findings.to_json())
            
            console.print(f"\n[bold green]📊 Analysis Complete: {len(merged_findings.findings)} finding(s) in changed code[/bold green]")
        else:
            console.print("[green]✅ No issues found in changed code[/green]")
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Git command failed: {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Analysis failed: {e}[/red]")


@app.command()
def init(
    path: str = typer.Argument(".", help="Project path to initialize"),
    with_hooks: bool = typer.Option(False, "--hooks", help="Install git hooks"),
    with_config: bool = typer.Option(True, "--config/--no-config", help="Create .patchpro.toml config"),
) -> None:
    """Initialize PatchPro for local development."""
    from pathlib import Path
    
    project_path = Path(path).resolve()
    console.print(f"[bold blue]🚀 Initializing PatchPro in {project_path}[/bold blue]")
    
    # Create config file
    if with_config:
        config_path = project_path / ".patchpro.toml"
        if config_path.exists():
            console.print(f"[yellow]Config file already exists: {config_path}[/yellow]")
        else:
            # Create default config
            config_content = '''[analysis]
tools = ["ruff", "semgrep"]
exclude_patterns = ["tests/", "__pycache__/", ".venv/", ".git/"]
max_findings_per_file = 50
severity_threshold = "info"

[ruff]
config_file = "pyproject.toml"
select = ["E", "F", "W", "C90", "I", "N", "UP", "B", "A", "C4", "SIM", "ARG", "PTH"]
line_length = 88
target_version = "py312"

[semgrep]
config = ".semgrep.yml"

[llm]
model = "gpt-4o-mini"
max_tokens = 4000
temperature = 0.1
api_key_env = "OPENAI_API_KEY"

[output]
artifacts_dir = ".patchpro"
format = "table"
include_patches = true
verbose = false
'''
            with open(config_path, 'w') as f:
                f.write(config_content)
            console.print(f"[green]✅ Created config file: {config_path}[/green]")
    
    # Create artifacts directory
    artifacts_dir = project_path / ".patchpro"
    artifacts_dir.mkdir(exist_ok=True)
    console.print(f"[green]✅ Created artifacts directory: {artifacts_dir}[/green]")
    
    # Update .gitignore
    gitignore_path = project_path / ".gitignore"
    gitignore_entries = [".patchpro/", "*.patch"]
    
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            existing = f.read()
        
        missing_entries = [entry for entry in gitignore_entries if entry not in existing]
        if missing_entries:
            with open(gitignore_path, 'a') as f:
                f.write("\n# PatchPro artifacts\\n")
                for entry in missing_entries:
                    f.write(f"{entry}\\n")
            console.print(f"[green]✅ Updated .gitignore with PatchPro entries[/green]")
    else:
        with open(gitignore_path, 'w') as f:
            f.write("# PatchPro artifacts\\n")
            for entry in gitignore_entries:
                f.write(f"{entry}\\n")
        console.print(f"[green]✅ Created .gitignore with PatchPro entries[/green]")
    
    # Install git hooks
    if with_hooks:
        git_dir = project_path / ".git"
        if git_dir.exists():
            hooks_dir = git_dir / "hooks"
            hooks_dir.mkdir(exist_ok=True)
            
            # Pre-commit hook
            pre_commit_hook = hooks_dir / "pre-commit"
            hook_content = '''#!/bin/bash
# PatchPro pre-commit hook
echo "🔍 Running PatchPro analysis on staged files..."

STAGED_FILES=$(git diff --cached --name-only | grep '\\.py$' | tr '\\n' ' ')

if [ -n "$STAGED_FILES" ]; then
    python -m patchpro_bot.cli diff-analyze --staged --format table
    
    # Check for critical issues
    python -m patchpro_bot.cli diff-analyze --staged --format json > .patchpro/staged_analysis.json
    CRITICAL=$(python -c "
import json
try:
    with open('.patchpro/staged_analysis.json') as f:
        data = json.load(f)
    critical = sum(1 for f in data.get('findings', []) if f.get('severity') == 'error')
    print(critical)
except:
    print(0)
")
    
    if [ "$CRITICAL" -gt 0 ]; then
        echo "❌ Found $CRITICAL critical issue(s). Run 'python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro' for fixes."
        echo "Or use --no-verify to bypass this check."
        exit 1
    fi
    
    echo "✅ PatchPro pre-commit check passed"
else
    echo "ℹ️ No Python files staged"
fi
'''
            
            with open(pre_commit_hook, 'w') as f:
                f.write(hook_content)
            pre_commit_hook.chmod(0o755)
            console.print(f"[green]✅ Installed pre-commit hook[/green]")
        else:
            console.print(f"[yellow]⚠️ Not a git repository, skipping hooks installation[/yellow]")
    
    console.print("\n[bold green]🎉 PatchPro initialization complete![/bold green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. [cyan]python -m patchpro_bot.cli analyze .[/cyan] - Analyze current code")
    console.print("2. [cyan]python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro[/cyan] - Generate patches")
    console.print("3. [cyan]python -m patchpro_bot.cli watch .[/cyan] - Watch for changes")
    console.print("4. Edit [cyan].patchpro.toml[/cyan] to customize settings")


@app.command()
def status(
    path: str = typer.Argument(".", help="Project path to check"),
) -> None:
    """Show PatchPro status for current project."""
    from pathlib import Path
    
    project_path = Path(path).resolve()
    console.print(f"[bold blue]📊 PatchPro Status for {project_path.name}[/bold blue]")
    
    # Check config
    config_path = project_path / ".patchpro.toml"
    if config_path.exists():
        console.print("[green]✅ Configuration file found[/green]")
        # Try to load and validate config
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()
            console.print(f"   📄 Config file: {config_path}")
        except Exception as e:
            console.print(f"[red]❌ Config file error: {e}[/red]")
    else:
        console.print("[yellow]⚠️ No configuration file (.patchpro.toml)[/yellow]")
        console.print("   Run [cyan]patchpro init[/cyan] to create one")
    
    # Check artifacts directory
    artifacts_dir = project_path / ".patchpro"
    if artifacts_dir.exists():
        console.print("[green]✅ Artifacts directory exists[/green]")
        
        # Check recent reports
        reports = list(artifacts_dir.glob("report*.md"))
        patches = list(artifacts_dir.glob("patch_*.diff"))
        
        if reports:
            latest_report = max(reports, key=lambda p: p.stat().st_mtime)
            console.print(f"   📊 Latest report: {latest_report.name}")
        
        if patches:
            latest_patch = max(patches, key=lambda p: p.stat().st_mtime)
            console.print(f"   🔧 Latest patch: {latest_patch.name}")
    else:
        console.print("[yellow]⚠️ No artifacts directory[/yellow]")
    
    # Check git hooks
    git_dir = project_path / ".git"
    if git_dir.exists():
        pre_commit_hook = git_dir / "hooks" / "pre-commit"
        if pre_commit_hook.exists():
            console.print("[green]✅ Git pre-commit hook installed[/green]")
        else:
            console.print("[yellow]⚠️ No git pre-commit hook[/yellow]")
            console.print("   Run [cyan]patchpro init --hooks[/cyan] to install")
    else:
        console.print("[dim]ℹ️ Not a git repository[/dim]")
    
    # Check tools availability
    console.print("\n[bold]Tool Availability:[/bold]")
    import subprocess
    
    tools = ["ruff", "semgrep", "python"]
    for tool in tools:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                console.print(f"[green]✅ {tool}[/green]: {version}")
            else:
                console.print(f"[red]❌ {tool}[/red]: Not working")
        except FileNotFoundError:
            console.print(f"[red]❌ {tool}[/red]: Not installed")
    
    # Check Python packages
    try:
        import patchpro_bot
        console.print(f"[green]✅ patchpro_bot[/green]: {patchpro_bot.__version__}")
    except ImportError:
        console.print("[red]❌ patchpro_bot: Not installed[/red]")


if __name__ == "__main__":
    app()