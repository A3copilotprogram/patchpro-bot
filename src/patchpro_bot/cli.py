"""Command-line interface for PatchPro Bot."""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from . import AgentCore, AgentConfig
from .analyzer import FindingsAnalyzer, NormalizedFindings

app = typer.Typer(help="PatchPro Bot - CI code-repair assistant")

console = Console()


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
        findings = reader.read_all_findings()
        
        rprint(f"[green]✅ Successfully validated {len(findings)} findings[/green]")
        
        # Show breakdown
        if findings:
            from .analysis import FindingAggregator
            aggregator = FindingAggregator(findings)
            summary = aggregator.get_summary()
            
            table = Table(title="Analysis Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Findings", str(summary["total_findings"]))
            table.add_row("Tools", ", ".join(summary["by_tool"].keys()))
            table.add_row("Affected Files", str(summary["affected_files"]))
            
            console.print(table)
        
    except Exception as e:
        rprint(f"[red]❌ Validation failed: {e}[/red]")
        raise typer.Exit(1)
        raise typer.Exit(1)
# ...existing CLI commands (analyze, normalize, validate_schema, demo, _display_results) ...

    
    analysis_dir = examples_dir / "artifact" / "analysis"
    artifact_dir = examples_dir / "artifact"
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        rprint("[yellow]Warning: No OpenAI API key found. Set OPENAI_API_KEY to run full demo.[/yellow]")
        rprint("Running validation only...")
        
        # Just validate the example data
        from .analysis import AnalysisReader, FindingAggregator
        
        reader = AnalysisReader(analysis_dir)
        findings = reader.read_all_findings()
        
        rprint(f"[green]✅ Demo data contains {len(findings)} findings[/green]")
        
        aggregator = FindingAggregator(findings)
        context = aggregator.to_prompt_context()
        
        rprint("\n[blue]Example prompt context:[/blue]")
        console.print(context[:500] + "..." if len(context) > 500 else context)
        
        return
    
    # Run full demo
    rprint("[blue]🎮 Running PatchPro Bot demo with example data...[/blue]")
    
    config = AgentConfig(
        analysis_dir=analysis_dir,
        artifact_dir=artifact_dir,
        base_dir=examples_dir,
        openai_api_key=api_key,


import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
import json
import os
from pathlib import Path
from typing import List, Optional

from . import AgentCore, AgentConfig
from .analyzer import FindingsAnalyzer, NormalizedFindings

app = typer.Typer(help="PatchPro Bot - CI code-repair assistant")
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
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    tool_outputs = {}
    if "ruff" in tools:
        console.print("Running Ruff analysis...")
        # Placeholder: replace with actual Ruff integration
        tool_outputs["ruff"] = []
    if "semgrep" in tools:
        console.print("Running Semgrep analysis...")
        # Placeholder: replace with actual Semgrep integration
        tool_outputs["semgrep"] = []
    if not tool_outputs:
        console.print("[yellow]⚠️  No analysis results found.[/yellow]")
        return
    console.print("Normalizing findings...")
    analyzer = FindingsAnalyzer()
    normalized_results = analyzer.normalize_findings(tool_outputs)
    if len(normalized_results) > 1:
        merged_findings = analyzer.merge_findings(normalized_results)
    else:
        merged_findings = normalized_results[0] if normalized_results else NormalizedFindings([], None)
    if format == "json":
        if output:
            merged_findings.save(output)
            console.print(f"[green]✅ Results saved to {output}[/green]")
        else:
            console.print(merged_findings.to_json())
    elif format == "table":
        _display_findings_table(merged_findings)
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
def validate_schema(
    findings_file: str = typer.Argument(..., help="Path to findings JSON file"),
) -> None:
    """Validate findings file against schema."""
    console.print(f"[bold blue]✅ Validating {findings_file}...[/bold blue]")
    try:
        findings_path = Path(findings_file)
        if not findings_path.exists():
            console.print(f"[red]❌ File not found: {findings_file}[/red]")
            raise typer.Exit(1)
        findings_data = json.loads(findings_path.read_text())
        required_keys = ["findings", "metadata"]
        for key in required_keys:
            if key not in findings_data:
                console.print(f"[red]❌ Missing required key: {key}[/red]")
                raise typer.Exit(1)
        if not isinstance(findings_data["findings"], list):
            console.print("[red]❌ 'findings' must be a list[/red]")
            raise typer.Exit(1)
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
        rprint("[yellow]Warning: No OpenAI API key found. Set OPENAI_API_KEY to run full demo.[/yellow]")
        rprint("Running validation only...")
        from .analysis import AnalysisReader, FindingAggregator
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
        results = agent.run()
        _display_results(results)
        if results["status"] == "success":
            rprint("[green]✅ Demo completed successfully![/green]")
            rprint(f"Check {artifact_dir} for generated patches and reports")
        else:
            rprint(f"[red]❌ Demo failed: {results.get('message', 'Unknown error')}")
    except Exception as e:
        rprint(f"[red]❌ Demo failed with error: {e}[/red]")
        raise typer.Exit(1)

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
    
