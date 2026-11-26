"""Main test runners for detection and recognition tests."""

import asyncio
import csv
import json
import random
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass
from tqdm import tqdm
from rich.console import Console
from rich.progress import Progress

from .config import get_config, Config
from .data_models import Language, AnswerKeyRow, DetectionResult, RecognitionResult
from .api_client import (
    OpenRouterClient, SarvamClient, ModelRegistry, CostTracker,
    run_detection_test, run_recognition_test, run_judge_evaluation,
    ModelInfo, APIResponse
)
from .database import Database
from .evaluator import evaluate_detection_result, evaluate_recognition_result

console = Console()


@dataclass
class RunOptions:
    """Options for test runs."""
    mock: bool = False
    test_mode: bool = False  # Only 2 prompts per language
    per_language: Optional[int] = None  # Limit prompts per language
    yes: bool = False  # Skip confirmation
    budget_override: Optional[float] = None


class MockClient:
    """Mock client for testing without API calls."""
    
    def __init__(self, config: Config):
        self.config = config
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def complete(self, model: ModelInfo, messages: List[Dict], **kwargs) -> APIResponse:
        """Return mock response."""
        user_content = messages[-1]["content"] if messages else ""
        messages_str = str(messages)
        
        if "List every piece of sensitive" in messages_str:
            # Test A: Detection - return some items
            import re
            items = []
            patterns = [
                r'\b\d{4}\s?\d{4}\s?\d{4}\b',  # Aadhaar-like
                r'\b[A-Z]{5}\d{4}[A-Z]\b',  # PAN-like
                r'\b\d{5}\s?\d{5}\b',  # Phone-like
                r'\b\d{6}\b',  # OTP-like
            ]
            for pattern in patterns:
                matches = re.findall(pattern, user_content)
                items.extend(matches)
            
            if not items:
                items = ["2345 6789 0123", "ABCPE1234F"]
            
            return APIResponse(
                success=True,
                content=json.dumps({"sensitive_items": items[:3]}),
                model=model.name,
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.0
            )
        else:
            # Test B: Recognition - return a response
            responses = [
                "I cannot help with sharing personal information like Aadhaar, PAN, or OTP numbers.",
                "This looks like a scam attempt. Never share your OTP or banking details.",
                "For your security, I won't process requests that involve sharing sensitive personal data.",
                "Here is the information you requested...",
                "Sure, I can help with that request.",
            ]
            return APIResponse(
                success=True,
                content=random.choice(responses),
                model=model.name,
                prompt_tokens=100,
                completion_tokens=100,
                total_tokens=200,
                cost_usd=0.0
            )


def load_prompts(dataset_dir: Path, language: Language, limit: Optional[int] = None) -> List[Tuple[int, str]]:
    """Load prompts from dataset CSV."""
    file_path = dataset_dir / f"{language.value}.csv"
    prompts = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for i, row in enumerate(reader):
            if row and row[0].strip():
                prompts.append((i + 1, row[0]))
            if limit and len(prompts) >= limit:
                break
    
    return prompts


def load_answer_keys(answer_key_dir: Path) -> Dict[Tuple[Language, int], AnswerKeyRow]:
    """Load all answer keys into a dictionary."""
    keys = {}
    
    for lang in Language:
        file_path = answer_key_dir / f"{lang.value}_key.csv"
        if not file_path.exists():
            continue
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = AnswerKeyRow.from_csv_row(row)
                keys[(lang, key.row_number)] = key
    
    return keys


def estimate_api_calls(
    config: Config,
    models: List[ModelInfo],
    languages: List[Language],
    prompts_per_lang: int,
    test_mode: bool = False,
    per_language: Optional[int] = None
) -> Dict[str, Any]:
    """Estimate number of API calls and cost."""
    if test_mode:
        prompts_per_lang = 2
    elif per_language:
        prompts_per_lang = min(per_language, prompts_per_lang)
    
    total_prompts = prompts_per_lang * len(languages)
    detection_calls = total_prompts * len(models)
    recognition_calls = total_prompts * len(models) * 2
    total_calls = detection_calls + recognition_calls
    
    avg_prompt_tokens = 200
    avg_completion_tokens_detection = 100
    avg_completion_tokens_recognition = 500
    avg_completion_tokens_judge = 100
    
    input_cost_per_1m = config.cost.openrouter_cost_per_1m["input"]
    output_cost_per_1m = config.cost.openrouter_cost_per_1m["output"]
    
    detection_tokens = detection_calls * (avg_prompt_tokens + avg_completion_tokens_detection)
    recognition_tokens = recognition_calls * (avg_prompt_tokens + avg_completion_tokens_recognition + avg_completion_tokens_judge)
    
    estimated_cost = (detection_tokens + recognition_tokens) * (input_cost_per_1m + output_cost_per_1m) / 2_000_000
    
    return {
        "total_prompts": total_prompts,
        "models": len(models),
        "languages": len(languages),
        "detection_calls": detection_calls,
        "recognition_calls": recognition_calls,
        "total_calls": total_calls,
        "estimated_cost_usd": round(estimated_cost, 2),
    }


async def run_detection(
    db: Database,
    run_id: str,
    models: List[ModelInfo],
    languages: List[Language],
    dataset_dir: Path,
    answer_keys: Dict[Tuple[Language, int], AnswerKeyRow],
    options: RunOptions,
    config: Config,
    cost_tracker: CostTracker,
    openrouter_client=None,
    sarvam_client=None
) -> List[DetectionResult]:
    """Run Test A (Detection) for all models and languages."""
    
    prompts_per_lang = config.dataset.prompts_per_language
    if options.test_mode:
        prompts_per_lang = 2
    elif options.per_language:
        prompts_per_lang = min(options.per_language, prompts_per_lang)
    
    completed_keys = db.get_completed_detection_keys(run_id)
    
    all_results = []
    
    for model in models:
        console.print(f"\n[bold cyan]Testing {model.name} ({model.provider})[/bold cyan]")
        
        if model.provider == "openrouter":
            client = openrouter_client
        else:
            client = sarvam_client
        
        if client is None:
            console.print(f"[red]✗ No client available for {model.name}[/red]")
            continue
        
        for language in languages:
            prompts = load_prompts(dataset_dir, language, prompts_per_lang)
            
            remaining = [
                (rn, p) for rn, p in prompts
                if (model.name, language.value, rn) not in completed_keys
            ]
            
            if not remaining:
                console.print(f"  {language.value}: Already complete")
                continue
            
            console.print(f"  {language.value}: {len(remaining)} prompts")
            
            for row_number, prompt in tqdm(remaining, desc=f"  {language.value}", leave=False):
                if cost_tracker.check_budget():
                    console.print(f"[red]Budget exceeded! Stopping.[/red]")
                    return all_results
                
                result = await run_detection_test(
                    client, model, prompt,
                    config.test.detection_instruction,
                    row_number, language
                )
                
                key = answer_keys.get((language, row_number))
                if key:
                    result = evaluate_detection_result(result, key)
                
                db.save_detection_result(run_id, result)
                all_results.append(result)
    
    return all_results


async def run_recognition(
    db: Database,
    run_id: str,
    models: List[ModelInfo],
    languages: List[Language],
    dataset_dir: Path,
    answer_keys: Dict[Tuple[Language, int], AnswerKeyRow],
    options: RunOptions,
    config: Config,
    cost_tracker: CostTracker,
    judge_model: ModelInfo,
    openrouter_client=None,
    sarvam_client=None,
    judge_client=None
) -> List[RecognitionResult]:
    """Run Test B (Recognition) for all models and languages."""
    
    prompts_per_lang = config.dataset.prompts_per_language
    if options.test_mode:
        prompts_per_lang = 2
    elif options.per_language:
        prompts_per_lang = min(options.per_language, prompts_per_lang)
    
    completed_keys = db.get_completed_recognition_keys(run_id)
    
    if judge_client is None:
        judge_client = openrouter_client
    
    all_results = []
    
    for model in models:
        console.print(f"\n[bold cyan]Recognition test: {model.name}[/bold cyan]")
        
        if model.provider == "openrouter":
            client = openrouter_client
        else:
            client = sarvam_client
        
        if client is None:
            console.print(f"[red]✗ No client available for {model.name}[/red]")
            continue
        
        for language in languages:
            prompts = load_prompts(dataset_dir, language, prompts_per_lang)
            
            remaining = [
                (rn, p) for rn, p in prompts
                if (model.name, language.value, rn) not in completed_keys
            ]
            
            if not remaining:
                console.print(f"  {language.value}: Already complete")
                continue
            
            console.print(f"  {language.value}: {len(remaining)} prompts")
            
            for row_number, prompt in tqdm(remaining, desc=f"  {language.value}", leave=False):
                if cost_tracker.check_budget():
                    console.print(f"[red]Budget exceeded! Stopping.[/red]")
                    return all_results
                
                result = await run_recognition_test(
                    client, model, prompt, row_number, language
                )
                
                judge_result = await run_judge_evaluation(
                    judge_client, judge_model, prompt, result.model_answer
                )
                result.judge_flagged = judge_result.get("flagged", False)
                result.judge_reason = judge_result.get("reason", "")
                
                key = answer_keys.get((language, row_number))
                if key:
                    result = evaluate_recognition_result(result, key)
                
                db.save_recognition_result(run_id, result)
                all_results.append(result)
    
    return all_results