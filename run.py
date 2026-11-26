#!/usr/bin/env python3
"""Main entry point for Privacy Metrics for AI Models in Indian Languages."""

import sys
import os
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from privacy_metrics.config import ConfigLoader, get_config, Config
from privacy_metrics.data_models import Language
from privacy_metrics.dataset_generator import DatasetBuilder, DatasetValidator
from privacy_metrics.api_client import (
    OpenRouterClient, SarvamClient, ModelRegistry, CostTracker, ModelInfo
)
from privacy_metrics.database import Database
from privacy_metrics.runner import (
    run_detection, run_recognition, RunOptions,
    load_answer_keys, estimate_api_calls
)
from privacy_metrics.metrics_calculator import (
    save_results_csv, ExcelReportWriter, generate_html_report,
    compute_metrics_by_group, compute_recognition_metrics_by_group,
    aggregate_item_metrics
)
from privacy_metrics.evaluator import (
    aggregate_metrics, aggregate_recognition_metrics
)

console = Console()

# Load environment variables
load_dotenv()


def get_api_keys() -> tuple:
    """Get API keys from environment."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    sarvam_key = os.getenv("SARVAM_API_KEY")
    return openrouter_key, sarvam_key


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Privacy Metrics for AI Models in Indian Languages."""
    pass


@cli.command()
def check():
    """Check API keys and model IDs."""
    console.print(Panel.fit("[bold]Checking Configuration[/bold]", border_style="blue"))
    
    config_loader = ConfigLoader("config.yaml")
    try:
        config = config_loader.load()
        console.print("[green]OK[/green] Config loaded successfully")
    except Exception as e:
        console.print(f"[red]FAIL[/red] Config error: {e}")
        return
    
    openrouter_key, sarvam_key = get_api_keys()
    
    if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
        console.print("[green]OK[/green] OPENROUTER_API_KEY found")
    else:
        console.print("[yellow]WARN[/yellow] OPENROUTER_API_KEY not set (required for ChatGPT, Gemini, Claude, DeepSeek)")
    
    if sarvam_key and sarvam_key != "your_sarvam_api_key_here":
        console.print("[green]OK[/green] SARVAM_API_KEY found")
    else:
        console.print("[yellow]WARN[/yellow] SARVAM_API_KEY not set (required for Sarvam-105B)")
    
    registry = ModelRegistry(config)
    table = Table(title="Models to Test")
    table.add_column("Model", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Model ID", style="green")
    
    for model in registry.models:
        table.add_row(model.name, model.provider, model.id)
    
    judge = registry.get_judge_model()
    table.add_row(f"{judge.name} (Judge)", judge.provider, judge.id)
    
    console.print(table)
    
    dataset_dir = Path("dataset")
    answer_key_dir = Path("answer_key")
    
    if dataset_dir.exists():
        csv_files = list(dataset_dir.glob("*.csv"))
        console.print(f"[green]OK[/green] Dataset directory exists with {len(csv_files)} language files")
    else:
        console.print("[yellow]WARN[/yellow] Dataset directory not found. Run 'build-dataset' first.")
    
    if answer_key_dir.exists():
        key_files = list(answer_key_dir.glob("*_key.csv"))
        console.print(f"[green]OK[/green] Answer key directory exists with {len(key_files)} key files")
    else:
        console.print("[yellow]WARN[/yellow] Answer key directory not found. Run 'build-dataset' first.")


@cli.command()
def build_dataset():
    """Create the 9 dataset CSVs + answer keys + review samples."""
    console.print(Panel.fit("[bold]Building Dataset[/bold]", border_style="blue"))
    
    config = get_config()
    
    dataset_dir = Path("dataset")
    answer_key_dir = Path("answer_key")
    review_dir = Path("review")
    
    builder = DatasetBuilder(config)
    builder.build_all(dataset_dir, answer_key_dir, review_dir)
    
    console.print("[green]OK[/green] Dataset build complete!")
    console.print(f"  Datasets: {dataset_dir}/")
    console.print(f"  Answer keys: {answer_key_dir}/")
    console.print(f"  Review samples: {review_dir}/")
    
    console.print("\n[bold]Validating...[/bold]")
    validator = DatasetValidator(config)
    results = validator.validate_all(dataset_dir, answer_key_dir)
    
    if results["valid"]:
        console.print("[green]OK[/green] All validation checks passed!")
    else:
        console.print("[red]FAIL[/red] Validation errors:")
        for error in results["errors"]:
            console.print(f"  - {error}")
    
    for warning in results["warnings"]:
        console.print(f"[yellow]WARN[/yellow] {warning}")


@cli.command()
def validate():
    """Check all dataset rules."""
    console.print(Panel.fit("[bold]Validating Dataset[/bold]", border_style="blue"))
    
    config = get_config()
    dataset_dir = Path("dataset")
    answer_key_dir = Path("answer_key")
    
    if not dataset_dir.exists():
        console.print("[red]FAIL[/red] Dataset directory not found. Run 'build-dataset' first.")
        return
    
    validator = DatasetValidator(config)
    results = validator.validate_all(dataset_dir, answer_key_dir)
    
    table = Table(title="Validation Results")
    table.add_column("Language", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Sensitive", justify="right")
    table.add_column("Non-Sensitive", justify="right")
    table.add_column("Status", style="bold")
    
    error_langs = [e.split(":")[0] for e in results["errors"]]
    for lang, stats in results["stats"].items():
        status = "[green]OK[/green]" if lang not in error_langs else "[red]ERROR[/red]"
        table.add_row(
            lang,
            str(stats.get("total_rows", 0)),
            str(stats.get("sensitive_count", 0)),
            str(stats.get("non_sensitive_count", 0)),
            status
        )
    
    console.print(table)
    
    if results["errors"]:
        console.print("\n[red]Errors:[/red]")
        for error in results["errors"]:
            console.print(f"  - {error}")
    
    if results["warnings"]:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in results["warnings"]:
            console.print(f"  - {warning}")
    
    if results["valid"]:
        console.print("\n[green]OK All validation checks passed![/green]")
    else:
        console.print("\n[red]✗ Validation failed![/red]")
        sys.exit(1)


async def _run_detect(options: RunOptions):
    """Internal async function for detection test."""
    config = get_config()
    
    dataset_dir = Path("dataset")
    answer_key_dir = Path("answer_key")
    db = Database(Path(config.output.database_file))
    
    answer_keys = load_answer_keys(answer_key_dir)
    registry = ModelRegistry(config)
    models = registry.models
    
    budget = options.budget_override or config.cost.budget_usd
    cost_tracker = CostTracker(budget, config)
    
    languages = [Language(l) for l in config.dataset.languages]
    prompts_per_lang = config.dataset.prompts_per_language
    if options.test_mode:
        prompts_per_lang = 2
    elif options.per_language:
        prompts_per_lang = min(options.per_language, prompts_per_lang)
    
    estimate = estimate_api_calls(config, models, languages, prompts_per_lang,
                                   options.test_mode, options.per_language)
    
    console.print(Panel.fit("[bold]Test A: Detection[/bold]", border_style="blue"))
    
    est_table = Table(title="Cost Estimate (Detection only)")
    est_table.add_column("Metric", style="cyan")
    est_table.add_column("Value", style="green")
    est_table.add_row("Total Prompts", str(estimate["total_prompts"]))
    est_table.add_row("Models", str(estimate["models"]))
    est_table.add_row("Detection Calls", str(estimate["detection_calls"]))
    est_table.add_row("Estimated Cost", f"${estimate['estimated_cost_usd']:.2f}")
    est_table.add_row("Budget", f"${budget:.2f}")
    console.print(est_table)
    
    if estimate["estimated_cost_usd"] > budget:
        console.print(f"[red]⚠ Estimated cost (${estimate['estimated_cost_usd']:.2f}) exceeds budget (${budget:.2f})![/red]")
        if not options.yes:
            if not Confirm.ask("Continue anyway?"):
                return
    elif not options.yes and not options.mock:
        if not Confirm.ask("Start detection test?"):
            return
    
    run_id = db.create_run("detect", hashlib.md5(str(config).encode()).hexdigest()[:8])
    console.print(f"Run ID: {run_id}")
    
    openrouter_key, sarvam_key = get_api_keys()
    
    if options.mock:
        from privacy_metrics.runner import MockClient
        or_client = MockClient(config)
        sv_client = MockClient(config)
        
        results = await run_detection(
            db, run_id, models, languages,
            dataset_dir, answer_keys, options, config, cost_tracker,
            openrouter_client=or_client, sarvam_client=sv_client
        )
    else:
        if not openrouter_key or openrouter_key == "your_openrouter_api_key_here":
            console.print("[red]✗ OPENROUTER_API_KEY not set. Use --mock for testing.[/red]")
            return
        if not sarvam_key or sarvam_key == "your_sarvam_api_key_here":
            console.print("[red]✗ SARVAM_API_KEY not set. Use --mock for testing.[/red]")
            return
        
        async with OpenRouterClient(config, cost_tracker, openrouter_key) as or_client, \
                   SarvamClient(config, cost_tracker, sarvam_key) as sv_client:
            results = await run_detection(
                db, run_id, models, languages,
                dataset_dir, answer_keys, options, config, cost_tracker,
                openrouter_client=or_client, sarvam_client=sv_client
            )
    
    db.complete_run(run_id, "completed", cost_tracker.total_cost)
    
    console.print(f"\n[green]OK Detection test complete![/green]")
    console.print(f"  Results: {len(results)} prompts tested")
    console.print(f"  Total cost: ${cost_tracker.total_cost:.4f}")
    console.print(f"  Run ID: {run_id}")
    
    return run_id


@cli.command()
@click.option('--mock', is_flag=True, help='Use mock responses (no API keys needed)')
@click.option('--test', is_flag=True, help='Test mode: 2 prompts per language')
@click.option('--per-language', type=int, help='Limit prompts per language')
@click.option('--yes', is_flag=True, help='Skip confirmation prompt')
@click.option('--budget', type=float, help='Override budget in USD')
def detect(mock, test, per_language, yes, budget):
    """Run Test A (Detection): models list sensitive items in prompts."""
    options = RunOptions(mock=mock, test_mode=test, per_language=per_language, yes=yes, budget_override=budget)
    asyncio.run(_run_detect(options))


async def _run_recognize(options: RunOptions):
    """Internal async function for recognition test."""
    config = get_config()
    
    dataset_dir = Path("dataset")
    answer_key_dir = Path("answer_key")
    db = Database(Path(config.output.database_file))
    
    answer_keys = load_answer_keys(answer_key_dir)
    registry = ModelRegistry(config)
    models = registry.models
    judge_model = registry.get_judge_model()
    
    budget = options.budget_override or config.cost.budget_usd
    cost_tracker = CostTracker(budget, config)
    
    languages = [Language(l) for l in config.dataset.languages]
    prompts_per_lang = config.dataset.prompts_per_language
    if options.test_mode:
        prompts_per_lang = 2
    elif options.per_language:
        prompts_per_lang = min(options.per_language, prompts_per_lang)
    
    estimate = estimate_api_calls(config, models, languages, prompts_per_lang,
                                   options.test_mode, options.per_language)
    
    console.print(Panel.fit("[bold]Test B: Recognition[/bold]", border_style="blue"))
    
    est_table = Table(title="Cost Estimate (Recognition only)")
    est_table.add_column("Metric", style="cyan")
    est_table.add_column("Value", style="green")
    est_table.add_row("Total Prompts", str(estimate["total_prompts"]))
    est_table.add_row("Models", str(estimate["models"]))
    est_table.add_row("Recognition Calls", str(estimate["recognition_calls"]))
    est_table.add_row("Estimated Cost", f"${estimate['estimated_cost_usd']:.2f}")
    est_table.add_row("Budget", f"${budget:.2f}")
    console.print(est_table)
    
    if estimate["estimated_cost_usd"] > budget:
        console.print(f"[red]⚠ Estimated cost exceeds budget![/red]")
        if not options.yes:
            if not Confirm.ask("Continue anyway?"):
                return
    elif not options.yes and not options.mock:
        if not Confirm.ask("Start recognition test?"):
            return
    
    run_id = db.create_run("recognize", hashlib.md5(str(config).encode()).hexdigest()[:8])
    console.print(f"Run ID: {run_id}")
    
    openrouter_key, sarvam_key = get_api_keys()
    
    if options.mock:
        from privacy_metrics.runner import MockClient
        or_client = MockClient(config)
        sv_client = MockClient(config)
        judge_client = MockClient(config)
        
        results = await run_recognition(
            db, run_id, models, languages,
            dataset_dir, answer_keys, options, config, cost_tracker,
            judge_model,
            openrouter_client=or_client, sarvam_client=sv_client, judge_client=judge_client
        )
    else:
        if not openrouter_key or openrouter_key == "your_openrouter_api_key_here":
            console.print("[red]✗ OPENROUTER_API_KEY not set. Use --mock for testing.[/red]")
            return
        if not sarvam_key or sarvam_key == "your_sarvam_api_key_here":
            console.print("[red]✗ SARVAM_API_KEY not set. Use --mock for testing.[/red]")
            return
        
        async with OpenRouterClient(config, cost_tracker, openrouter_key) as or_client, \
                   SarvamClient(config, cost_tracker, sarvam_key) as sv_client:
            
            judge_client = or_client if judge_model.provider == "openrouter" else sv_client
            
            results = await run_recognition(
                db, run_id, models, languages,
                dataset_dir, answer_keys, options, config, cost_tracker,
                judge_model,
                openrouter_client=or_client, sarvam_client=sv_client, judge_client=judge_client
            )
    
    db.complete_run(run_id, "completed", cost_tracker.total_cost)
    
    console.print(f"\n[green]OK Recognition test complete![/green]")
    console.print(f"  Results: {len(results)} prompts tested")
    console.print(f"  Total cost: ${cost_tracker.total_cost:.4f}")
    console.print(f"  Run ID: {run_id}")
    
    return run_id


@cli.command()
@click.option('--mock', is_flag=True, help='Use mock responses (no API keys needed)')
@click.option('--test', is_flag=True, help='Test mode: 2 prompts per language')
@click.option('--per-language', type=int, help='Limit prompts per language')
@click.option('--yes', is_flag=True, help='Skip confirmation prompt')
@click.option('--budget', type=float, help='Override budget in USD')
def recognize(mock, test, per_language, yes, budget):
    """Run Test B (Recognition): models respond normally, AI judge evaluates privacy flagging."""
    options = RunOptions(mock=mock, test_mode=test, per_language=per_language, yes=yes, budget_override=budget)
    asyncio.run(_run_recognize(options))


@cli.command()
@click.option('--detection-run', type=str, help='Run ID for detection results')
@click.option('--recognition-run', type=str, help='Run ID for recognition results')
def metrics(detection_run, recognition_run):
    """Calculate metrics and write results.xlsx + report.html."""
    console.print(Panel.fit("[bold]Calculating Metrics & Generating Reports[/bold]", border_style="blue"))
    
    config = get_config()
    db = Database(Path(config.output.database_file))
    
    if not detection_run:
        detection_run = db.get_latest_run("detect")
        if detection_run:
            console.print(f"Using latest detection run: {detection_run}")
        else:
            console.print("[red]FAIL No detection run found. Run 'detect' first.[/red]")
            return
    
    if not recognition_run:
        recognition_run = db.get_latest_run("recognize")
        if recognition_run:
            console.print(f"Using latest recognition run: {recognition_run}")
        else:
            console.print("[red]FAIL No recognition run found. Run 'recognize' first.[/red]")
            return
    
    detection_results = db.get_detection_results(detection_run)
    recognition_results = db.get_recognition_results(recognition_run)
    
    console.print(f"Loaded {len(detection_results)} detection results")
    console.print(f"Loaded {len(recognition_results)} recognition results")
    
    answer_key_dir = Path("answer_key")
    answer_keys = load_answer_keys(answer_key_dir)
    
    languages = [Language(l) for l in config.dataset.languages]
    registry = ModelRegistry(config)
    models = registry.models
    
    det_model_metrics = compute_metrics_by_group(detection_results, answer_keys, "model")
    det_lang_metrics = compute_metrics_by_group(detection_results, answer_keys, "language")
    det_script_metrics = compute_metrics_by_group(detection_results, answer_keys, "script")
    det_type_metrics = aggregate_item_metrics(detection_results)
    
    rec_model_metrics = compute_recognition_metrics_by_group(recognition_results, answer_keys, "model")
    rec_lang_metrics = compute_recognition_metrics_by_group(recognition_results, answer_keys, "language")
    rec_script_metrics = compute_recognition_metrics_by_group(recognition_results, answer_keys, "script")
    
    save_results_csv(
        detection_results, recognition_results,
        Path(config.output.detection_answers),
        Path(config.output.recognition_answers)
    )
    
    excel_writer = ExcelReportWriter(Path(config.output.excel_file))
    
    excel_writer.write_model_metrics("Detection by model", det_model_metrics)
    excel_writer.write_language_metrics("Detection by language", det_lang_metrics)
    excel_writer.write_script_metrics("Detection by script", det_script_metrics)
    excel_writer.write_type_recall("Detection recall by type", det_type_metrics)
    excel_writer.write_lookalike_fpr("Detection lookalike FPR", det_type_metrics)
    
    excel_writer.write_model_metrics("Recognition by model", rec_model_metrics)
    excel_writer.write_language_metrics("Recognition by language", rec_lang_metrics)
    excel_writer.write_script_metrics("Recognition by script", rec_script_metrics)
    
    excel_writer.add_charts(det_model_metrics, det_lang_metrics)
    excel_writer.save()
    
    config_summary = {
        "total_prompts": config.dataset.prompts_per_language,
        "languages_tested": len(languages),
    }
    
    generate_html_report(
        det_model_metrics, det_lang_metrics, det_script_metrics,
        det_type_metrics, det_type_metrics,
        rec_model_metrics, rec_lang_metrics, rec_script_metrics,
        Path(config.output.html_report),
        config_summary
    )
    
    console.print("\n[green]OK Metrics calculation and report generation complete![/green]")
    console.print(f"  Excel: {config.output.excel_file}")
    console.print(f"  HTML:  {config.output.html_report}")
    console.print(f"  Detection CSV: {config.output.detection_answers}")
    console.print(f"  Recognition CSV: {config.output.recognition_answers}")


@cli.command()
@click.option('--mock', is_flag=True, help='Use mock responses (no API keys needed)')
@click.option('--test', is_flag=True, help='Test mode: 2 prompts per language')
@click.option('--per-language', type=int, help='Limit prompts per language')
@click.option('--yes', is_flag=True, help='Skip confirmation prompts')
@click.option('--budget', type=float, help='Override budget in USD')
def all(mock, test, per_language, yes, budget):
    """Run detect + recognize + metrics in sequence."""
    options = RunOptions(mock=mock, test_mode=test, per_language=per_language, yes=yes, budget_override=budget)
    
    console.print(Panel.fit("[bold]Running Full Pipeline[/bold]", border_style="blue"))
    
    detection_run = asyncio.run(_run_detect(options))
    if not detection_run:
        return
    
    recognition_run = asyncio.run(_run_recognize(options))
    if not recognition_run:
        return
    
    ctx = click.get_current_context()
    ctx.invoke(metrics, detection_run=detection_run, recognition_run=recognition_run)


if __name__ == "__main__":
    cli()