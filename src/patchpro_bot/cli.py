"""Command-line interface for PatchPro Bot."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import logging
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from . import AgentCore, AgentConfig
from .analyzer import FindingsAnalyzer, NormalizedFindings
from .analysis import AnalysisReader, FindingAggregator

console = Console()
app = typer.Typer(
    name="patchpro",
    help="PatchPro: CI code-repair assistant",
    add_completion=False,
)

@app.command()
def run(
    analysis_dir: Path = typer.Option(
        Path("artifact/analysis"),
        "--analysis-dir", "-a",
        help="Directory containing analysis JSON files"
    ),
    artifact_dir: Path = typer.Option(
        Path("artifact"),
        "--artifact-dir", "-o",
        help="Output directory for patches and reports"
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key", "-k",
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    ),
    model: str = typer.Option(
        "gpt-4o-mini",
        "--model", "-m",
        help="OpenAI model to use"
    ),
    max_findings: int = typer.Option(
        20,
        "--max-findings", "-f",
        help="Maximum number of findings to process"
    ),
    combine_patches: bool = typer.Option(
        True,
        "--combine/--separate",
        help="Combine patches into single file or create separate files"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging"
    ),
):
    """Run the PatchPro Bot pipeline."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        rprint(
            "[red]Error: OpenAI API key is required. "
            "Set OPENAI_API_KEY env var or use --api-key[/red]"
        )
        raise typer.Exit(1)
    config = AgentConfig(
        analysis_dir=analysis_dir,
        artifact_dir=artifact_dir,
        openai_api_key=api_key,
        llm_model=model,
        max_findings=max_findings,
        combine_patches=combine_patches,
    )
    if not analysis_dir.exists():
        rprint(
            f"[red]Error: Analysis directory does not exist: {analysis_dir}[/red]"
        )
        raise typer.Exit(1)
    json_files = list(analysis_dir.glob("*.json"))
    if not json_files:
        rprint(
            f"[yellow]Warning: No JSON files found in {analysis_dir}[/yellow]"
        )
        rprint("Expected files like ruff_output.json, semgrep_output.json")
    rprint("[blue]\ud83d\ude80 Starting PatchPro Bot pipeline...[/blue]")
    try:
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        _display_results(results)
        if results["status"] == "success":
            rprint("[green]\u2705 Pipeline completed successfully![/green]")
        else:
            rprint(f"[red]\u274c Pipeline failed: {results.get('message', 'Unknown error')}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]\u274c Pipeline failed with error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)

# ...rest of the CLI commands and helpers as in the incoming branch...
 
@app.command()
def validate(
    analysis_dir: Path = typer.Option(
        Path("artifact/analysis"),
        "--analysis-dir", "-a",
        help="Directory containing analysis JSON files"
    ),
):
    """Validate analysis JSON files."""
    if not analysis_dir.exists():
        rprint(f"[red]Error: Directory does not exist: {analysis_dir}[/red]")
        raise typer.Exit(1)
    reader = AnalysisReader(analysis_dir)
    try:
        findings = reader.read_all_findings()
        rprint(f"[green]✅ Successfully validated {len(findings)} findings[/green]")
        if findings:
            aggregator = FindingAggregator(findings)
            summary = aggregator.get_summary()
            table = Table(title="Analysis Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Total Findings", str(summary["total_findings"]))
            table.add_row("Tools", ", ".join(summary["by_tool"].keys()))
            table.add_row("Affected Files", str(summary["affected_files"]))
            console.print(table)
    except Exception as exc:
        rprint(f"[red]❌ Validation failed: {exc}[/red]")
        raise typer.Exit(1) from exc
>>>>>>> 6fb41f8 (docs: add summary of recent CI/devex and agent core changes (2025-10-01))

@app.command()
def demo():
    """Run demo with example data."""
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    if not examples_dir.exists():
        rprint("[red]Error: Examples directory not found[/red]")
        raise typer.Exit(1)
    analysis_dir = examples_dir / "artifact" / "analysis"
    artifact_dir = examples_dir / "artifact"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        rprint(
            "[yellow]Warning: No OpenAI API key found. "
            "Set OPENAI_API_KEY to run full demo.[/yellow]"
        )
        rprint("Running validation only...")
        reader = AnalysisReader(analysis_dir)
        findings = reader.read_all_findings()
        rprint(f"[green]✅ Demo data contains {len(findings)} findings[/green]")
        aggregator = FindingAggregator(findings)
        context = aggregator.to_prompt_context()
        rprint("\n[blue]Example prompt context:[/blue]")
        console.print(context[:500] + "..." if len(context) > 500 else context)
        return
    rprint("[blue]🎮 Running PatchPro Bot demo with example data...[/blue]")
    config = AgentConfig(
        analysis_dir=analysis_dir,
        artifact_dir=artifact_dir,
        base_dir=examples_dir,
        openai_api_key=api_key,
        max_findings=10,
    )
    try:
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        _display_results(results)
        if results["status"] == "success":
            rprint("[green]✅ Demo completed successfully![/green]")
            rprint(f"Check {artifact_dir} for generated patches and reports")
        else:
            rprint(f"[red]❌ Demo failed: {results.get('message', 'Unknown error')}[/red]")
    except Exception as e:
        rprint(f"[red]❌ Demo failed with error: {e}[/red]")
        raise typer.Exit(1)

<<<<<<< HEAD
def _display_findings_table(findings: NormalizedFindings) -> None:
    if not findings.findings:
        console.print("[yellow]No findings to display.[/yellow]")
        return
    summary = Panel(
        f"Tool: {findings.metadata.tool}\n"
        f"Version: {findings.metadata.version}\n"
        f"Timestamp: {findings.metadata.timestamp}\n"
        f"Total Findings: {findings.metadata.total_findings}",
        title="Analysis Summary",
        border_style="blue"
    )
    console.print(summary)
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Line", style="green", justify="right")
    table.add_column("Rule", style="yellow")
    table.add_column("Severity", style="red")
    table.add_column("Category", style="blue")
    table.add_column("Message", style="white")
    sorted_findings = sorted(
        findings.findings,
        key=lambda f: (getattr(f.location, 'file', ''), getattr(f.location, 'line', 0))
    )
    for finding in sorted_findings:
        message = finding.message
        if len(message) > 80:
            message = message[:77] + "..."
        severity_style = {
            "error": "[red]ERROR[/red]",
            "warning": "[yellow]WARNING[/yellow]",
            "info": "[blue]INFO[/blue]",
            "note": "[dim]NOTE[/dim]"
        }.get(getattr(finding, 'severity', ''), getattr(finding, 'severity', ''))
        table.add_row(
            getattr(finding.location, 'file', ''),
            str(getattr(finding.location, 'line', '')),
            getattr(finding, 'rule_id', ''),
            severity_style,
            getattr(finding, 'category', '').upper(),
            message
        )
    console.print(table)

def _display_results(results: dict):
=======
def _display_results(results: dict):
    """Display pipeline results in a nice format."""
>>>>>>> 6fb41f8 (docs: add summary of recent CI/devex and agent core changes (2025-10-01))
    table = Table(title="Pipeline Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Status", results["status"])
    if results["status"] == "success":
        table.add_row("Findings Processed", str(results.get("findings_count", 0)))
        table.add_row("Fixes Generated", str(results.get("fixes_generated", 0)))
        table.add_row("Patches Written", str(results.get("patches_written", 0)))
        if results.get("report_path"):
            table.add_row("Report", results["report_path"])
        if results.get("combined_patch"):
            table.add_row("Combined Patch", results["combined_patch"])
    else:
        table.add_row("Error", results.get("message", "Unknown error"))
    console.print(table)
 
>>>>>>> 6fb41f8 (docs: add summary of recent CI/devex and agent core changes (2025-10-01))
