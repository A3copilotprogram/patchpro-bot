# BEGIN CONFLICT: Duplicate run function with different logic
@app.command()
def run(
    analysis_dir: Path = typer.Option(Path("conflict/analysis"), "--analysis-dir", help="Conflicting analysis dir option"),
    verbose: bool = typer.Option(True, "--verbose", help="Conflicting verbose default"),
):
    """[CONFLICT] This is a conflicting run function for simulation purposes."""
    rprint("[red]This is the conflicting run function![/red]")
# END CONFLICT


import asyncio
import os
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from . import AgentCore, AgentConfig

app = typer.Typer(help="PatchPro Bot - CI code-repair assistant")
console = Console()

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
        import logging
        logging.basicConfig(level=logging.DEBUG)
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        rprint("[red]Error: OpenAI API key is required. Set OPENAI_API_KEY env var or use --api-key[/red]")
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
        rprint(f"[red]Error: Analysis directory does not exist: {analysis_dir}[/red]")
        raise typer.Exit(1)
    json_files = list(analysis_dir.glob("*.json"))
    if not json_files:
        rprint(f"[yellow]Warning: No JSON files found in {analysis_dir}[/yellow]")
        rprint("Expected files like ruff_output.json, semgrep_output.json")
    rprint("[blue]🚀 Starting PatchPro Bot pipeline...[/blue]")
    try:
        agent = AgentCore(config)
        results = agent.run()
        _display_results(results)
        if results["status"] == "success":
            rprint("[green]✅ Pipeline completed successfully![/green]")
        else:
            rprint(f"[red]❌ Pipeline failed: {results.get('message', 'Unknown error')}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]❌ Pipeline failed with error: {e}[/red]")
        if verbose:
            import traceback
            console.print_exception()
        raise typer.Exit(1)

# ...add other commands (analyze, normalize, validate_schema, demo) as needed, following the same pattern...

if __name__ == "__main__":
    app()
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
    
    # Setup logging level
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Get API key
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        rprint("[red]Error: OpenAI API key is required. Set OPENAI_API_KEY env var or use --api-key[/red]")
        raise typer.Exit(1)
    
    # Create configuration
    config = AgentConfig(
        analysis_dir=analysis_dir,
        artifact_dir=artifact_dir,
        openai_api_key=api_key,
        llm_model=model,
        max_findings=max_findings,
        combine_patches=combine_patches,
    )
    
    # Check analysis directory
    if not analysis_dir.exists():
        rprint(f"[red]Error: Analysis directory does not exist: {analysis_dir}[/red]")
        raise typer.Exit(1)
    
    # Check for analysis files
    json_files = list(analysis_dir.glob("*.json"))
    if not json_files:
        rprint(f"[yellow]Warning: No JSON files found in {analysis_dir}[/yellow]")
        rprint("Expected files like ruff_output.json, semgrep_output.json")
    
    # Run the agent
    rprint("[blue]🚀 Starting PatchPro Bot pipeline...[/blue]")
    
    try:
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        
        # Display results
        _display_results(results)
        
        if results["status"] == "success":
            rprint("[green]✅ Pipeline completed successfully![/green]")
        else:
            rprint(f"[red]❌ Pipeline failed: {results.get('message', 'Unknown error')}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Pipeline failed with error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


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
    
    from .analysis import AnalysisReader
    
    reader = AnalysisReader(analysis_dir)
    
    # Try to read all findings
    try:
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


@app.command()
def demo():
    """Run demo with example data."""
    
    # Use example data
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    
    if not examples_dir.exists():
        rprint("[red]Error: Examples directory not found[/red]")
        raise typer.Exit(1)
    
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


def _display_results(results: dict):
    """Display pipeline results in a nice format."""
    
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



if __name__ == "__main__":
    app()
