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
) -> None:
    """Run complete CI pipeline with LLM integration."""
    
    console.print("[bold blue]🚀 Running PatchPro CI Pipeline...[/bold blue]")
    
    try:
        # Setup paths
        artifacts_path = Path(artifacts_dir)
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        base_path = Path(base_dir) if base_dir else Path.cwd()
        analysis_path = artifacts_path / "analysis"
        
        # Run agent core
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


if __name__ == "__main__":
    app()