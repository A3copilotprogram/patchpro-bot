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

from .analyzer import FindingsAnalyzer, NormalizedFindings, Finding, Metadata
from .agent_core import AgentCore, AgentConfig

app = typer.Typer(
    name="patchpro",
    help="PatchPro: CI code-repair assistant with LLM integration",
    add_completion=False,
)

console = Console()


def _detect_tool_from_file(findings_path: Path) -> str:
    """Detect which tool generated the findings file."""
    filename = findings_path.name.lower()
    
    # Try to detect from filename
    if 'ruff' in filename:
        return 'ruff'
    elif 'semgrep' in filename:
        return 'semgrep'
    elif 'pylint' in filename:
        return 'pylint'
    elif 'mypy' in filename:
        return 'mypy'
    
    # Try to detect from content
    try:
        with open(findings_path, 'r') as f:
            content = f.read(500)  # Read first 500 chars
            content_lower = content.lower()
            
            if '"check":' in content_lower or '"code":' in content_lower and '"message":' in content_lower:
                return 'ruff'
            elif '"check_id":' in content_lower or 'semgrep' in content_lower:
                return 'semgrep'
            elif 'pylint' in content_lower:
                return 'pylint'
            elif 'mypy' in content_lower:
                return 'mypy'
    except:
        pass
    
    # Default to generic
    return 'static-analysis'


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
    from_findings: List[str] = typer.Option(None, "--from-findings", "-f", help="Use existing findings files instead of running tools"),
) -> None:
    """Run complete CI pipeline with LLM integration.
    
    Supports two modes:
    1. Run tools mode (default): Runs ruff/semgrep and generates patches
    2. From findings mode: Uses existing tool outputs to generate patches
    
    Examples:
        # Mode 1: Run everything
        patchpro run-ci
        
        # Mode 2: Use existing findings
        patchpro run-ci --from-findings ruff.json --from-findings semgrep.json
    """
    
    console.print("[bold blue]🚀 Running PatchPro CI Pipeline...[/bold blue]")
    
    try:
        # Setup paths
        artifacts_path = Path(artifacts_dir)
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        base_path = Path(base_dir) if base_dir else Path.cwd()
        analysis_path = artifacts_path / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        
        # Determine mode: from-findings or run-tools
        if from_findings:
            # MODE 2: Use existing findings
            console.print("[bold cyan]📂 Loading existing findings...[/bold cyan]")
            
            tool_outputs = {}
            for findings_file in from_findings:
                findings_path = Path(findings_file)
                if not findings_path.exists():
                    console.print(f"[red]❌ Findings file not found: {findings_file}[/red]")
                    continue
                
                # Try to detect tool type from filename or content
                tool_name = _detect_tool_from_file(findings_path)
                console.print(f"Loading {tool_name} findings from {findings_file}")
                
                with open(findings_path, 'r') as f:
                    tool_outputs[tool_name] = json.load(f)
            
            if not tool_outputs:
                console.print("[red]❌ No valid findings files provided[/red]")
                raise typer.Exit(1)
            
            console.print(f"[green]✅ Loaded findings from {len(tool_outputs)} tool(s)[/green]")
        else:
            # MODE 1: Run tools (original behavior)
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
        
        # Common path: Normalize findings (works for both modes)
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


@app.command()
def generate_patches(
    findings_files: List[str] = typer.Argument(..., help="Paths to tool output files (ruff.json, semgrep.json, etc.)"),
    artifacts_dir: str = typer.Option("artifact", "--artifacts", "-a", help="Artifacts directory for patches"),
    base_dir: Optional[str] = typer.Option(None, "--base-dir", help="Base directory for code context"),
) -> None:
    """Generate AI-powered patches from existing static analysis findings.
    
    This command is designed for teams that already run static analysis tools
    in their CI/CD pipeline. Instead of re-running the tools, PatchPro reads
    the existing findings and generates patches.
    
    Examples:
        # Generate patches from ruff and semgrep outputs
        patchpro generate-patches ruff.json semgrep.json
        
        # With custom artifacts location
        patchpro generate-patches findings/*.json --artifacts patches/
        
        # Typical CI integration
        ruff check --output-format json . > ruff.json
        semgrep --json . > semgrep.json
        patchpro generate-patches ruff.json semgrep.json
    """
    
    console.print("[bold blue]🤖 Generating patches from existing findings...[/bold blue]")
    
    try:
        # Setup paths
        artifacts_path = Path(artifacts_dir)
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        base_path = Path(base_dir) if base_dir else Path.cwd()
        analysis_path = artifacts_path / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        
        # Load all findings files
        console.print(f"[cyan]📂 Loading findings from {len(findings_files)} file(s)...[/cyan]")
        
        tool_outputs = {}
        for findings_file in findings_files:
            findings_path = Path(findings_file)
            if not findings_path.exists():
                console.print(f"[yellow]⚠️  Skipping missing file: {findings_file}[/yellow]")
                continue
            
            # Detect tool type
            tool_name = _detect_tool_from_file(findings_path)
            console.print(f"  • Loading {tool_name} findings from {findings_path.name}")
            
            try:
                with open(findings_path, 'r') as f:
                    tool_data = json.load(f)
                    tool_outputs[tool_name] = tool_data
                    
                # Also save to analysis directory for AgentCore
                tool_filename = f"{tool_name}_output.json"
                (analysis_path / tool_filename).write_text(json.dumps(tool_data, indent=2))
                
            except json.JSONDecodeError:
                console.print(f"[yellow]⚠️  Skipping invalid JSON: {findings_file}[/yellow]")
                continue
        
        if not tool_outputs:
            console.print("[red]❌ No valid findings files found[/red]")
            raise typer.Exit(1)
        
        console.print(f"[green]✅ Loaded findings from {len(tool_outputs)} tool(s)[/green]")
        
        # Normalize findings
        console.print("[cyan]🔄 Normalizing findings...[/cyan]")
        analyzer = FindingsAnalyzer()
        normalized_results = analyzer.normalize_findings(tool_outputs)
        normalized_findings = analyzer.merge_findings(normalized_results)
        
        # Save normalized findings
        normalized_findings.save(str(analysis_path / "normalized_findings.json"))
        console.print(f"[green]✅ Normalized {len(normalized_findings.findings)} findings[/green]")
        
        if len(normalized_findings.findings) == 0:
            console.print("[yellow]ℹ️  No findings to generate patches for[/yellow]")
            return
        
        # Run LLM pipeline
        console.print("[bold cyan]🤖 Generating AI patches...[/bold cyan]")
        config = AgentConfig(
            analysis_dir=analysis_path,
            artifact_dir=artifacts_path,
            base_dir=base_path,
        )
        
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        
        console.print(f"[green]✅ Patch generation complete: {results}[/green]")
        
        # Show output locations
        patches = list(artifacts_path.glob("patch_*.diff"))
        if patches:
            console.print("\n[bold]Generated patches:[/bold]")
            for patch in patches:
                console.print(f"  📄 {patch}")
        
    except Exception as e:
        console.print(f"[red]❌ Patch generation failed: {e}[/red]")
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
        
        # Handle git worktrees (where .git is a file pointing to actual git dir)
        actual_git_dir = git_dir
        if git_dir.is_file():
            # Read gitdir location from .git file
            gitdir_line = git_dir.read_text().strip()
            if gitdir_line.startswith('gitdir: '):
                actual_git_dir = Path(gitdir_line[8:])  # Remove 'gitdir: ' prefix
                if not actual_git_dir.is_absolute():
                    actual_git_dir = (project_path / actual_git_dir).resolve()
        
        if actual_git_dir.exists() and actual_git_dir.is_dir():
            hooks_dir = actual_git_dir / "hooks"
            hooks_dir.mkdir(exist_ok=True, parents=True)
            
            # Post-index-change hook (triggers on git add)
            post_index_hook = hooks_dir / "post-index-change"
            post_index_content = '''#!/bin/bash
# PatchPro post-index-change hook
# Triggers background analysis when files are staged

# Get staged Python files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep '\\.py$')

if [ -n "$STAGED_PY" ]; then
    # Start background analysis (non-blocking)
    nohup python -m patchpro_bot.cli analyze-staged --async > /dev/null 2>&1 &
fi
'''
            
            with open(post_index_hook, 'w') as f:
                f.write(post_index_content)
            post_index_hook.chmod(0o755)
            console.print(f"[green]✅ Installed post-index-change hook (triggers on git add)[/green]")
            
            # Smart pre-commit hook (checks status and shows interactive prompt)
            pre_commit_hook = hooks_dir / "pre-commit"
            pre_commit_content = '''#!/bin/bash
# PatchPro smart pre-commit hook
# Checks if analysis has findings and shows interactive prompt

# Check if there are staged Python files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep '\\.py$')

if [ -n "$STAGED_PY" ]; then
    # Run interactive prompt (checks status.json)
    python -m patchpro_bot.cli pre-commit-prompt
    exit $?
fi

# No Python files staged, allow commit
exit 0
'''
            
            with open(pre_commit_hook, 'w') as f:
                f.write(pre_commit_content)
            pre_commit_hook.chmod(0o755)
            console.print(f"[green]✅ Installed smart pre-commit hook (interactive prompt)[/green]")
        else:
            console.print(f"[yellow]⚠️ Not a git repository, skipping hooks installation[/yellow]")
    
    console.print("\n[bold green]🎉 PatchPro initialization complete![/bold green]")
    
    if with_hooks:
        console.print("\n[bold cyan]Async Workflow Enabled:[/bold cyan]")
        console.print("• [dim]git add file.py[/dim] → PatchPro analyzes in background")
        console.print("• [dim]git commit[/dim] → Shows findings with interactive prompt")
        console.print("• Non-blocking, CI-like experience!")
    
    console.print("\n[bold]Commands:[/bold]")
    console.print("1. [cyan]python -m patchpro_bot.cli check-status[/cyan] - Check analysis status")
    console.print("2. [cyan]python -m patchpro_bot.cli analyze-staged --with-llm[/cyan] - Generate patches for staged files")
    console.print("3. [cyan]python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro[/cyan] - Full analysis")
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


@app.command()
def analyze_staged(
    async_mode: bool = typer.Option(False, "--async", help="Run analysis in background"),
    with_llm: bool = typer.Option(False, "--with-llm", help="Include LLM patch generation"),
    artifacts_dir: str = typer.Option(".patchpro", "--artifacts", "-a", help="Artifacts directory"),
) -> None:
    """Analyze staged files (triggered by git add)."""
    import subprocess
    from datetime import datetime
    
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    
    # Get staged Python files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True
        )
        staged_files = [f for f in result.stdout.strip().split('\n') if f.endswith('.py')]
    except subprocess.CalledProcessError:
        console.print("[red]❌ Failed to get staged files[/red]")
        return
    
    if not staged_files:
        # Write idle status
        _write_status(artifacts_path, {
            "status": "idle",
            "message": "No Python files staged",
            "timestamp": datetime.now().isoformat()
        })
        return
    
    if async_mode:
        # Run in background
        import multiprocessing
        process = multiprocessing.Process(
            target=_run_staged_analysis,
            args=(staged_files, artifacts_path, with_llm)
        )
        process.start()
        console.print(f"[dim]🤖 PatchPro analyzing {len(staged_files)} file(s) in background...[/dim]")
    else:
        # Run synchronously
        _run_staged_analysis(staged_files, artifacts_path, with_llm)


def _run_staged_analysis(staged_files: List[str], artifacts_path: Path, with_llm: bool = False):
    """Run analysis on staged files (internal function)."""
    from datetime import datetime
    
    # Write running status
    _write_status(artifacts_path, {
        "status": "running",
        "files": staged_files,
        "started_at": datetime.now().isoformat()
    })
    
    try:
        # Run analysis
        analyzer = FindingsAnalyzer()
        tool_outputs = {}
        
        # Run ruff
        ruff_output = _run_ruff(staged_files, None, artifacts_path)
        if ruff_output:
            tool_outputs["ruff"] = ruff_output
        
        # Run semgrep
        semgrep_output = _run_semgrep(staged_files, None, artifacts_path)
        if semgrep_output:
            tool_outputs["semgrep"] = semgrep_output
        
        # Normalize findings
        if tool_outputs:
            normalized_results = analyzer.normalize_findings(tool_outputs)
            merged_findings = analyzer.merge_findings(normalized_results)
            
            # Save findings
            findings_file = artifacts_path / "findings.json"
            merged_findings.save(str(findings_file))
            
            # Count by severity
            critical_count = sum(1 for f in merged_findings.findings if f.severity == "error")
            warning_count = sum(1 for f in merged_findings.findings if f.severity == "warning")
            
            # Optionally run LLM for patch generation
            patches_available = False
            if with_llm and len(merged_findings.findings) > 0:
                try:
                    config = AgentConfig(
                        analysis_dir=artifacts_path,
                        artifact_dir=artifacts_path,
                        base_dir=Path.cwd(),
                    )
                    agent = AgentCore(config)
                    asyncio.run(agent.run())
                    patches_available = True
                except Exception as e:
                    console.print(f"[yellow]⚠️  LLM patch generation failed: {e}[/yellow]")
            
            # Write completed status
            _write_status(artifacts_path, {
                "status": "completed",
                "findings_count": len(merged_findings.findings),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "patches_available": patches_available,
                "files_analyzed": staged_files,
                "completed_at": datetime.now().isoformat()
            })
        else:
            # No findings
            _write_status(artifacts_path, {
                "status": "completed",
                "findings_count": 0,
                "critical_count": 0,
                "warning_count": 0,
                "patches_available": False,
                "files_analyzed": staged_files,
                "completed_at": datetime.now().isoformat()
            })
    
    except Exception as e:
        # Write error status
        _write_status(artifacts_path, {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })


def _write_status(artifacts_path: Path, status_data: dict):
    """Write status to status.json file."""
    status_file = artifacts_path / "status.json"
    with open(status_file, 'w') as f:
        json.dump(status_data, f, indent=2)


def _read_status(artifacts_path: Path) -> dict:
    """Read status from status.json file."""
    status_file = artifacts_path / "status.json"
    if status_file.exists():
        with open(status_file, 'r') as f:
            return json.load(f)
    return {"status": "idle"}


@app.command()
def check_status(
    artifacts_dir: str = typer.Option(".patchpro", "--artifacts", "-a", help="Artifacts directory"),
) -> None:
    """Check PatchPro analysis status."""
    artifacts_path = Path(artifacts_dir)
    status = _read_status(artifacts_path)
    
    if status["status"] == "idle":
        console.print("[dim]No active analysis[/dim]")
    elif status["status"] == "running":
        console.print("[yellow]🤖 Analysis running...[/yellow]")
        if "files" in status:
            console.print(f"   Files: {', '.join(status['files'])}")
    elif status["status"] == "completed":
        findings_count = status.get("findings_count", 0)
        critical_count = status.get("critical_count", 0)
        
        if findings_count == 0:
            console.print("[green]✅ No issues found[/green]")
        else:
            console.print(f"[yellow]⚠️  Found {findings_count} issue(s)[/yellow]")
            if critical_count > 0:
                console.print(f"   🔴 {critical_count} critical")
            if status.get("patches_available"):
                console.print("   🔧 Patches available")
    elif status["status"] == "error":
        console.print(f"[red]❌ Analysis failed: {status.get('error', 'Unknown error')}[/red]")


@app.command()
def pre_commit_prompt(
    artifacts_dir: str = typer.Option(".patchpro", "--artifacts", "-a", help="Artifacts directory"),
) -> None:
    """Interactive prompt for pre-commit when findings exist."""
    from rich.prompt import Prompt
    
    artifacts_path = Path(artifacts_dir)
    status = _read_status(artifacts_path)
    
    if status["status"] == "running":
        console.print("[yellow]🤖 PatchPro is still analyzing...[/yellow]")
        choice = Prompt.ask(
            "Action",
            choices=["wait", "commit", "cancel"],
            default="commit"
        )
        
        if choice == "wait":
            import time
            console.print("Waiting for analysis...")
            for i in range(10):
                time.sleep(1)
                status = _read_status(artifacts_path)
                if status["status"] != "running":
                    break
                console.print(f"  {i+1}s...")
            
            if status["status"] == "running":
                console.print("[yellow]Analysis still running, proceeding with commit[/yellow]")
                sys.exit(0)
            else:
                # Re-run prompt with completed status
                pre_commit_prompt(artifacts_dir)
                return
        elif choice == "commit":
            console.print("[dim]Proceeding with commit...[/dim]")
            sys.exit(0)
        else:
            console.print("[yellow]Commit cancelled[/yellow]")
            sys.exit(1)
    
    elif status["status"] == "completed":
        findings_count = status.get("findings_count", 0)
        critical_count = status.get("critical_count", 0)
        
        if findings_count == 0:
            console.print("[green]✅ No issues found, proceeding with commit[/green]")
            sys.exit(0)
        
        # Show findings
        console.print(f"\n[yellow]⚠️  PatchPro found {findings_count} issue(s)[/yellow]")
        if critical_count > 0:
            console.print(f"   🔴 {critical_count} critical issue(s)")
        if status.get("patches_available"):
            console.print(f"   🔧 Patches available in {artifacts_dir}/")
        
        console.print()
        
        choice = Prompt.ask(
            "Action",
            choices=["view", "apply", "commit", "cancel"],
            default="view"
        )
        
        if choice == "view":
            # Show findings table
            findings_file = artifacts_path / "findings.json"
            if findings_file.exists():
                findings_data = json.loads(findings_file.read_text())
                # Create NormalizedFindings from dict
                findings_list = [
                    Finding(
                        file=f['file'],
                        line=f['line'],
                        column=f.get('column', 1),
                        severity=f['severity'],
                        code=f['code'],
                        message=f['message'],
                        tool=f['tool']
                    )
                    for f in findings_data['findings']
                ]
                metadata = Metadata(
                    tool=findings_data['metadata']['tool'],
                    version=findings_data['metadata'].get('version', 'unknown'),
                    total_findings=findings_data['metadata']['total_findings']
                )
                findings = NormalizedFindings(findings=findings_list, metadata=metadata)
                _display_findings_table(findings)
            
            # Ask again
            choice2 = Prompt.ask(
                "Action",
                choices=["apply", "commit", "cancel"],
                default="commit"
            )
            choice = choice2
        
        if choice == "apply":
            # Apply patches
            patches = list(artifacts_path.glob("patch_combined_*.diff"))
            if patches:
                latest_patch = max(patches, key=lambda p: p.stat().st_mtime)
                console.print(f"[cyan]Applying patch: {latest_patch.name}[/cyan]")
                result = subprocess.run(
                    ["git", "apply", str(latest_patch)],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    console.print("[green]✅ Patch applied successfully[/green]")
                    console.print("[yellow]Please stage the changes and commit again[/yellow]")
                    sys.exit(1)  # Stop commit so user can stage patch changes
                else:
                    console.print(f"[red]❌ Failed to apply patch: {result.stderr}[/red]")
                    console.print("[yellow]Proceeding with commit anyway[/yellow]")
                    sys.exit(0)
            else:
                console.print("[yellow]No patches found[/yellow]")
                sys.exit(0)
        
        elif choice == "commit":
            console.print("[dim]Proceeding with commit despite findings...[/dim]")
            sys.exit(0)
        else:
            console.print("[yellow]Commit cancelled[/yellow]")
            sys.exit(1)
    
    else:
        # Idle or error - allow commit
        console.print("[dim]No analysis results, proceeding with commit[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    app()