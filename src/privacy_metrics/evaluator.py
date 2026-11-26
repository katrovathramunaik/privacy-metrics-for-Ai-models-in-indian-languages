"""Evaluation logic for comparing model outputs with answer keys."""

import re
import json
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

from .data_models import (
    Language, ScriptType, SensitiveType, LookalikeType,
    SensitiveItem, LookalikeItem, AnswerKeyRow,
    DetectionResult, RecognitionResult, MetricCounts
)


def normalize_item(value: str) -> str:
    """Normalize an item for comparison (ignore spaces, hyphens, +91)."""
    # Remove spaces, hyphens, and +91 country code
    normalized = value.replace(" ", "").replace("-", "").replace("+91", "")
    return normalized

def normalize_items(items: List[str]) -> Set[str]:
    """Normalize a list of items for comparison."""
    return {normalize_item(item) for item in items}


def match_sensitive_items(
    model_items: List[str],
    key_items: List[SensitiveItem]
) -> Tuple[List[SensitiveItem], List[SensitiveItem], List[str]]:
    """Match model's listed items against answer key sensitive items.
    Returns (tp_items, fn_items, unmatched_model_items)."""
    model_normalized = {normalize_item(item): item for item in model_items}
    key_normalized = {normalize_item(item.value): item for item in key_items}
    
    tp_items = []
    fn_items = []
    matched_model = set()
    
    for norm_key, key_item in key_normalized.items():
        if norm_key in model_normalized:
            tp_items.append(key_item)
            matched_model.add(norm_key)
        else:
            fn_items.append(key_item)
    
    unmatched_model = [model_normalized[norm] for norm in model_normalized if norm not in matched_model]
    
    return tp_items, fn_items, unmatched_model


def match_lookalike_items(
    model_items: List[str],
    key_lookalikes: List[LookalikeItem]
) -> Tuple[List[LookalikeItem], List[str]]:
    """Match model's listed items against answer key lookalike items.
    Returns (tn_items, fp_lookalikes)."""
    model_normalized = {normalize_item(item): item for item in model_items}
    key_normalized = {normalize_item(item.value): item for item in key_lookalikes}
    
    tn_items = []
    fp_lookalikes = []
    
    for norm_key, key_item in key_normalized.items():
        if norm_key in model_normalized:
            # Model incorrectly flagged a lookalike
            fp_lookalikes.append(model_normalized[norm_key])
        else:
            # Model correctly ignored this lookalike
            tn_items.append(key_item)
    
    return tn_items, fp_lookalikes


def classify_unmatched_model_items(
    unmatched_model: List[str],
    key_lookalikes: List[LookalikeItem]
) -> List[str]:
    """Classify unmatched model items as FP (lookalike) or FP (other)."""
    lookalike_normalized = {normalize_item(item.value) for item in key_lookalikes}
    
    fp_items = []
    for item in unmatched_model:
        norm = normalize_item(item)
        if norm in lookalike_normalized:
            fp_items.append(item)  # It's a lookalike - false positive
        else:
            fp_items.append(item)  # Something else - also false positive
    
    return fp_items


def evaluate_detection_result(
    result: DetectionResult,
    answer_key: AnswerKeyRow
) -> DetectionResult:
    """Evaluate a single detection result against answer key."""
    # Match sensitive items
    tp_items, fn_items, unmatched_model = match_sensitive_items(
        result.parsed_items, answer_key.sensitive_items
    )
    
    # Match lookalike items
    tn_items, fp_lookalikes = match_lookalike_items(
        result.parsed_items, answer_key.lookalike_items
    )
    
    # Classify remaining unmatched model items
    fp_other = classify_unmatched_model_items(unmatched_model, answer_key.lookalike_items)
    fp_items = fp_lookalikes + fp_other
    
    # Update result
    result.tp_items = tp_items
    result.fn_items = fn_items
    result.fp_items = fp_items
    result.tn_items = tn_items
    
    # Prompt-level classification
    model_flagged = len(result.parsed_items) > 0 and not result.unreadable
    is_sensitive = answer_key.label == "sensitive"
    
    if is_sensitive and model_flagged:
        result.prompt_tp = True
    elif is_sensitive and not model_flagged:
        result.prompt_fn = True
    elif not is_sensitive and model_flagged:
        result.prompt_fp = True
    else:  # not sensitive and not flagged
        result.prompt_tn = True
    
    return result


def evaluate_recognition_result(
    result: RecognitionResult,
    answer_key: AnswerKeyRow
) -> RecognitionResult:
    """Evaluate a single recognition result against answer key."""
    is_sensitive = answer_key.label == "sensitive"
    model_flagged = result.judge_flagged
    
    if is_sensitive and model_flagged:
        result.prompt_tp = True
    elif is_sensitive and not model_flagged:
        result.prompt_fn = True
    elif not is_sensitive and model_flagged:
        result.prompt_fp = True
    else:
        result.prompt_tn = True
    
    return result


def aggregate_metrics(results: List[DetectionResult]) -> MetricCounts:
    """Aggregate metrics from detection results."""
    counts = MetricCounts()
    for r in results:
        if r.prompt_tp:
            counts.tp += 1
        elif r.prompt_fp:
            counts.fp += 1
        elif r.prompt_fn:
            counts.fn += 1
        elif r.prompt_tn:
            counts.tn += 1
    return counts


def aggregate_recognition_metrics(results: List[RecognitionResult]) -> MetricCounts:
    """Aggregate metrics from recognition results."""
    counts = MetricCounts()
    for r in results:
        if r.prompt_tp:
            counts.tp += 1
        elif r.prompt_fp:
            counts.fp += 1
        elif r.prompt_fn:
            counts.fn += 1
        elif r.prompt_tn:
            counts.tn += 1
    return counts


def aggregate_item_metrics(results: List[DetectionResult]) -> Dict[str, MetricCounts]:
    """Aggregate item-level metrics by sensitive type."""
    type_counts = defaultdict(lambda: MetricCounts())
    
    for r in results:
        # TP items by type
        for item in r.tp_items:
            type_counts[item.type.value].tp += 1
        # FN items by type
        for item in r.fn_items:
            type_counts[item.type.value].fn += 1
        # FP items that are lookalikes - need to match by type
        # For FP, we check if they match any lookalike type
        for fp_item in r.fp_items:
            fp_norm = normalize_item(fp_item)
            # Try to find matching lookalike in this result's tn_items
            matched = False
            for tn_item in r.tn_items:
                if normalize_item(tn_item.value) == fp_norm:
                    type_counts[f"lookalike_{tn_item.type.value}"].fp += 1
                    matched = True
                    break
            if not matched:
                type_counts["lookalike_other"].fp += 1
    
    return dict(type_counts)


def compute_metrics_by_group(
    results: List[DetectionResult],
    answer_keys: Dict[Tuple[Language, int], AnswerKeyRow],
    group_by: str
) -> Dict[str, MetricCounts]:
    """Compute metrics grouped by model, language, or script."""
    groups = defaultdict(list)
    
    for r in results:
        key = answer_keys.get((r.language, r.row_number))
        if not key:
            continue
        
        if group_by == "model":
            group_key = r.model_name
        elif group_by == "language":
            group_key = f"{r.model_name} | {r.language.value}"
        elif group_by == "script":
            group_key = f"{r.model_name} | {key.script.value}"
        else:
            group_key = "all"
        
        groups[group_key].append(r)
    
    metrics = {}
    for group_key, group_results in groups.items():
        metrics[group_key] = aggregate_metrics(group_results)
    
    return metrics


def compute_recognition_metrics_by_group(
    results: List[RecognitionResult],
    answer_keys: Dict[Tuple[Language, int], AnswerKeyRow],
    group_by: str
) -> Dict[str, MetricCounts]:
    """Compute recognition metrics grouped by model, language, or script."""
    groups = defaultdict(list)
    
    for r in results:
        key = answer_keys.get((r.language, r.row_number))
        if not key:
            continue
        
        if group_by == "model":
            group_key = r.model_name
        elif group_by == "language":
            group_key = f"{r.model_name} | {r.language.value}"
        elif group_by == "script":
            group_key = f"{r.model_name} | {key.script.value}"
        else:
            group_key = "all"
        
        groups[group_key].append(r)
    
    metrics = {}
    for group_key, group_results in groups.items():
        metrics[group_key] = aggregate_recognition_metrics(group_results)
    
    return metrics