"""Metrics calculation and Excel/HTML report generation."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from jinja2 import Environment, FileSystemLoader

from .data_models import (
    Language, ScriptType, SensitiveType, LookalikeType,
    MetricCounts, DetectionResult, RecognitionResult, AnswerKeyRow
)
from .evaluator import (
    aggregate_metrics, aggregate_recognition_metrics,
    aggregate_item_metrics, compute_metrics_by_group,
    compute_recognition_metrics_by_group
)


def detection_results_to_dataframe(results: List[DetectionResult]) -> pd.DataFrame:
    """Convert detection results to DataFrame for CSV export."""
    rows = []
    for r in results:
        rows.append({
            "model": r.model_name,
            "language": r.language.value,
            "row_number": r.row_number,
            "prompt": r.prompt[:500],  # Truncate for CSV
            "model_response": r.model_response[:500],
            "parsed_items": json.dumps(r.parsed_items, ensure_ascii=False),
            "unreadable": r.unreadable,
            "tp_items": json.dumps([item.to_dict() for item in r.tp_items], ensure_ascii=False),
            "fn_items": json.dumps([item.to_dict() for item in r.fn_items], ensure_ascii=False),
            "fp_items": json.dumps(r.fp_items, ensure_ascii=False),
            "tn_items": json.dumps([item.to_dict() for item in r.tn_items], ensure_ascii=False),
            "prompt_tp": r.prompt_tp,
            "prompt_fp": r.prompt_fp,
            "prompt_fn": r.prompt_fn,
            "prompt_tn": r.prompt_tn,
        })
    return pd.DataFrame(rows)


def recognition_results_to_dataframe(results: List[RecognitionResult]) -> pd.DataFrame:
    """Convert recognition results to DataFrame for CSV export."""
    rows = []
    for r in results:
        rows.append({
            "model": r.model_name,
            "language": r.language.value,
            "row_number": r.row_number,
            "prompt": r.prompt[:500],
            "model_answer": r.model_answer[:500],
            "judge_flagged": r.judge_flagged,
            "judge_reason": r.judge_reason,
            "prompt_tp": r.prompt_tp,
            "prompt_fp": r.prompt_fp,
            "prompt_fn": r.prompt_fn,
            "prompt_tn": r.prompt_tn,
        })
    return pd.DataFrame(rows)


def save_results_csv(detection_results: List[DetectionResult],
                     recognition_results: List[RecognitionResult],
                     detection_path: Path,
                     recognition_path: Path):
    """Save results to CSV files."""
    detection_df = detection_results_to_dataframe(detection_results)
    recognition_df = recognition_results_to_dataframe(recognition_results)
    
    detection_df.to_csv(detection_path, index=False, encoding='utf-8')
    recognition_df.to_csv(recognition_path, index=False, encoding='utf-8')
    
    print(f"Saved detection answers to {detection_path}")
    print(f"Saved recognition answers to {recognition_path}")


class ExcelReportWriter:
    """Write metrics to Excel with multiple sheets and formatting."""
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.wb = Workbook()
        self.header_font = Font(bold=True, color="FFFFFF")
        self.header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        self.header_alignment = Alignment(horizontal="center", wrap_text=True)
        self.thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def _write_sheet_header(self, ws, headers: List[str], row: int = 1):
        """Write formatted header row."""
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = self.header_alignment
            cell.border = self.thin_border
    
    def _write_data_rows(self, ws, data: List[List], start_row: int, start_col: int = 1):
        """Write data rows with formatting."""
        for row_idx, row_data in enumerate(data, start_row):
            for col_idx, value in enumerate(row_data, start_col):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = self.thin_border
                cell.alignment = Alignment(horizontal="center")
                if isinstance(value, float):
                    cell.number_format = '0.0000'
    
    def _auto_width(self, ws, min_width: int = 10, max_width: int = 50):
        """Auto-adjust column widths."""
        for col in ws.columns:
            max_length = min_width
            for cell in col:
                if cell.value:
                    max_length = max(max_length, min(len(str(cell.value)) + 2, max_width))
            ws.column_dimensions[col[0].column_letter].width = max_length
    
    def write_model_metrics(self, sheet_name: str, metrics: Dict[str, MetricCounts],
                            title: str = "Metrics by Model"):
        """Write model-level metrics sheet."""
        ws = self.wb.create_sheet(sheet_name)
        
        headers = ["Model", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy", "FPR", "Miss Rate"]
        self._write_sheet_header(ws, headers)
        
        data = []
        for model, counts in metrics.items():
            data.append([
                model,
                counts.tp, counts.fp, counts.fn, counts.tn,
                counts.precision(), counts.recall(), counts.f1(),
                counts.accuracy(), counts.fpr(), counts.miss_rate()
            ])
        
        self._write_data_rows(ws, data, 2)
        self._auto_width(ws)
    
    def write_language_metrics(self, sheet_name: str, metrics: Dict[str, MetricCounts],
                                title: str = "Metrics by Language"):
        """Write language-level metrics sheet."""
        ws = self.wb.create_sheet(sheet_name)
        
        headers = ["Model | Language", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy", "FPR", "Miss Rate"]
        self._write_sheet_header(ws, headers)
        
        data = []
        for key, counts in metrics.items():
            data.append([
                key,
                counts.tp, counts.fp, counts.fn, counts.tn,
                counts.precision(), counts.recall(), counts.f1(),
                counts.accuracy(), counts.fpr(), counts.miss_rate()
            ])
        
        self._write_data_rows(ws, data, 2)
        self._auto_width(ws)
    
    def write_script_metrics(self, sheet_name: str, metrics: Dict[str, MetricCounts]):
        """Write script-level metrics sheet."""
        ws = self.wb.create_sheet(sheet_name)
        
        headers = ["Model | Script", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy", "FPR", "Miss Rate"]
        self._write_sheet_header(ws, headers)
        
        data = []
        for key, counts in metrics.items():
            data.append([
                key,
                counts.tp, counts.fp, counts.fn, counts.tn,
                counts.precision(), counts.recall(), counts.f1(),
                counts.accuracy(), counts.fpr(), counts.miss_rate()
            ])
        
        self._write_data_rows(ws, data, 2)
        self._auto_width(ws)
    
    def write_type_recall(self, sheet_name: str, type_metrics: Dict[str, MetricCounts]):
        """Write recall by sensitive data type sheet."""
        ws = self.wb.create_sheet(sheet_name)
        
        headers = ["Sensitive Type", "TP", "FN", "Recall"]
        self._write_sheet_header(ws, headers)
        
        data = []
        for stype in SensitiveType:
            key = stype.value
            if key in type_metrics:
                counts = type_metrics[key]
                data.append([key, counts.tp, counts.fn, counts.recall()])
            else:
                data.append([key, 0, 0, 0.0])
        
        self._write_data_rows(ws, data, 2)
        self._auto_width(ws)
    
    def write_lookalike_fpr(self, sheet_name: str, type_metrics: Dict[str, MetricCounts]):
        """Write false positive rate by lookalike type sheet."""
        ws = self.wb.create_sheet(sheet_name)
        
        headers = ["Lookalike Type", "FP", "TN", "FPR"]
        self._write_sheet_header(ws, headers)
        
        data = []
        for ltype in LookalikeType:
            key = f"lookalike_{ltype.value}"
            if key in type_metrics:
                counts = type_metrics[key]
                data.append([ltype.value, counts.fp, counts.tn, counts.fpr()])
            else:
                data.append([ltype.value, 0, 0, 0.0])
        
        # Add other
        if "lookalike_other" in type_metrics:
            counts = type_metrics["lookalike_other"]
            data.append(["Other", counts.fp, counts.tn, counts.fpr()])
        
        self._write_data_rows(ws, data, 2)
        self._auto_width(ws)
    
    def add_charts(self, detection_model_metrics: Dict[str, MetricCounts],
                   detection_lang_metrics: Dict[str, MetricCounts]):
        """Add charts to the workbook."""
        # F1 by Model chart
        ws_f1 = self.wb.create_sheet("F1 by Model")
        ws_f1.append(["Model", "F1 Score"])
        for model, counts in detection_model_metrics.items():
            ws_f1.append([model, counts.f1()])
        
        chart = BarChart()
        chart.title = "F1 Score by Model (Detection)"
        chart.y_axis.title = "F1 Score"
        chart.x_axis.title = "Model"
        data = Reference(ws_f1, min_col=2, min_row=1, max_row=len(detection_model_metrics)+1)
        cats = Reference(ws_f1, min_col=1, min_row=2, max_row=len(detection_model_metrics)+1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.shape = 4
        ws_f1.add_chart(chart, "D2")
        
        # Recall by Language grouped bar chart
        ws_recall = self.wb.create_sheet("Recall by Language")
        
        # Extract unique models and languages
        models = set()
        languages = set()
        for key in detection_lang_metrics.keys():
            parts = key.split(" | ")
            if len(parts) == 2:
                models.add(parts[0])
                languages.add(parts[1])
        
        models = sorted(list(models))
        languages = sorted(list(languages))
        
        # Header
        ws_recall.append(["Language"] + models)
        
        for lang in languages:
            row = [lang]
            for model in models:
                key = f"{model} | {lang}"
                if key in detection_lang_metrics:
                    row.append(detection_lang_metrics[key].recall())
                else:
                    row.append(0)
            ws_recall.append(row)
        
        chart2 = BarChart()
        chart2.type = "col"
        chart2.grouping = "clustered"
        chart2.title = "Recall by Language (Detection)"
        chart2.y_axis.title = "Recall"
        chart2.x_axis.title = "Language"
        
        data = Reference(ws_recall, min_col=2, min_row=1, max_col=len(models)+1, max_row=len(languages)+1)
        cats = Reference(ws_recall, min_col=1, min_row=2, max_row=len(languages)+1)
        chart2.add_data(data, titles_from_data=True)
        chart2.set_categories(cats)
        chart2.shape = 4
        ws_recall.add_chart(chart2, "D2")
    
    def save(self):
        """Save workbook."""
        # Remove default sheet
        if "Sheet" in self.wb.sheetnames:
            self.wb.remove(self.wb["Sheet"])
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.wb.save(self.output_path)
        print(f"Excel report saved to {self.output_path}")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Metrics Report</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2F5496; border-bottom: 3px solid #2F5496; padding-bottom: 10px; }
        h2 { color: #333; margin-top: 40px; }
        h3 { color: #555; }
        .summary { background: #e8f0fe; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-card { background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #2F5496; }
        .metric-label { color: #666; font-size: 0.9em; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.9em; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background: #2F5496; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .chart-container { width: 100%; height: 500px; margin: 30px 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Privacy Metrics for AI Models in Indian Languages</h1>
        
        <div class="summary">
            <h2>Executive Summary</h2>
            <p>{{ summary_text }}</p>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{{ detection_models_tested }}</div>
                    <div class="metric-label">Models Tested (Detection)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ recognition_models_tested }}</div>
                    <div class="metric-label">Models Tested (Recognition)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ languages_tested }}</div>
                    <div class="metric-label">Languages Tested</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ total_prompts }}</div>
                    <div class="metric-label">Total Prompts per Model</div>
                </div>
            </div>
        </div>
        
        <h2>Detection Test (Test A) Results</h2>
        
        <h3>Overall by Model</h3>
        {{ detection_model_table | safe }}
        
        <div class="chart-container" id="f1-chart"></div>
        
        <h3>By Language</h3>
        {{ detection_lang_table | safe }}
        
        <div class="chart-container" id="recall-lang-chart"></div>
        
        <h3>By Script</h3>
        {{ detection_script_table | safe }}
        
        <h3>Recall by Sensitive Data Type</h3>
        {{ detection_type_table | safe }}
        
        <h3>False Positive Rate by Lookalike Type</h3>
        {{ detection_lookalike_table | safe }}
        
        <h2>Recognition Test (Test B) Results</h2>
        
        <h3>Overall by Model</h3>
        {{ recognition_model_table | safe }}
        
        <h3>By Language</h3>
        {{ recognition_lang_table | safe }}
        
        <h3>By Script</h3>
        {{ recognition_script_table | safe }}
        
        <div class="footer">
            <p>Generated by Privacy Metrics for AI Models in Indian Languages</p>
            <p>Test A (Detection): Models asked to list sensitive items in prompts</p>
            <p>Test B (Recognition): Models respond normally, AI judge evaluates if they flagged privacy risk</p>
            <p>Metrics: Precision = TP/(TP+FP), Recall = TP/(TP+FN), F1 = 2PR/(P+R), Accuracy = (TP+TN)/Total, FPR = FP/(FP+TN), Miss Rate = FN/(TP+FN)</p>
        </div>
    </div>
    
    <script>
        // F1 by Model Chart
        var f1Data = {{ f1_chart_data | safe }};
        Plotly.newPlot('f1-chart', [{
            x: f1Data.models,
            y: f1Data.f1_scores,
            type: 'bar',
            marker: {color: '#2F5496'},
            name: 'F1 Score'
        }], {
            title: 'F1 Score by Model (Detection Test)',
            yaxis: {title: 'F1 Score', range: [0, 1]},
            xaxis: {title: 'Model'}
        });
        
        // Recall by Language Chart
        var recallData = {{ recall_lang_chart_data | safe }};
        var traces = [];
        recallData.models.forEach(function(model, i) {
            traces.push({
                x: recallData.languages,
                y: recallData.values[i],
                name: model,
                type: 'bar'
            });
        });
        Plotly.newPlot('recall-lang-chart', traces, {
            title: 'Recall by Language (Detection Test)',
            yaxis: {title: 'Recall', range: [0, 1]},
            xaxis: {title: 'Language'},
            barmode: 'group'
        });
    </script>
</body>
</html>
"""


def generate_html_report(
    detection_model_metrics: Dict[str, MetricCounts],
    detection_lang_metrics: Dict[str, MetricCounts],
    detection_script_metrics: Dict[str, MetricCounts],
    detection_type_metrics: Dict[str, MetricCounts],
    detection_lookalike_metrics: Dict[str, MetricCounts],
    recognition_model_metrics: Dict[str, MetricCounts],
    recognition_lang_metrics: Dict[str, MetricCounts],
    recognition_script_metrics: Dict[str, MetricCounts],
    output_path: Path,
    config_summary: Dict[str, Any]
):
    """Generate HTML report with interactive charts."""
    
    def metrics_to_table(metrics: Dict[str, MetricCounts], columns: List[str]) -> str:
        """Convert metrics dict to HTML table."""
        html = "<table><tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr>"
        for key, counts in metrics.items():
            html += "<tr>"
            html += f"<td>{key}</td>"
            for col in columns[1:]:
                val = getattr(counts, col.lower().replace(" ", "_"))
                if callable(val):
                    val = val()
                if isinstance(val, float):
                    html += f"<td>{val:.4f}</td>"
                else:
                    html += f"<td>{val}</td>"
            html += "</tr>"
        html += "</table>"
        return html
    
    # Prepare table data
    det_model_cols = ["Model", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy", "FPR", "Miss Rate"]
    det_lang_cols = ["Model | Language", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy", "FPR", "Miss Rate"]
    
    # F1 chart data
    f1_chart_data = {
        "models": list(detection_model_metrics.keys()),
        "f1_scores": [counts.f1() for counts in detection_model_metrics.values()]
    }
    
    # Recall by language chart data
    models = set()
    languages = set()
    for key in detection_lang_metrics.keys():
        parts = key.split(" | ")
        if len(parts) == 2:
            models.add(parts[0])
            languages.add(parts[1])
    models = sorted(list(models))
    languages = sorted(list(languages))
    
    recall_values = []
    for model in models:
        model_vals = []
        for lang in languages:
            key = f"{model} | {lang}"
            if key in detection_lang_metrics:
                model_vals.append(detection_lang_metrics[key].recall())
            else:
                model_vals.append(0)
        recall_values.append(model_vals)
    
    recall_lang_chart_data = {
        "models": models,
        "languages": languages,
        "values": recall_values
    }
    
    # Summary text
    best_model = max(detection_model_metrics.items(), key=lambda x: x[1].f1())[0] if detection_model_metrics else "N/A"
    summary_text = f"This report evaluates {len(detection_model_metrics)} AI models on their ability to detect and recognize sensitive personal information in 9 Indian languages. "
    summary_text += f"The best performing model on Detection Test (F1) is {best_model}. "
    summary_text += f"Models were tested on {config_summary.get('total_prompts', 1000)} prompts per language across {config_summary.get('languages_tested', 9)} languages."
    
    # Render template
    env = Environment()
    template = env.from_string(HTML_TEMPLATE)
    
    html = template.render(
        summary_text=summary_text,
        detection_models_tested=len(detection_model_metrics),
        recognition_models_tested=len(recognition_model_metrics),
        languages_tested=config_summary.get('languages_tested', 9),
        total_prompts=config_summary.get('total_prompts', 1000),
        detection_model_table=metrics_to_table(detection_model_metrics, det_model_cols),
        detection_lang_table=metrics_to_table(detection_lang_metrics, det_lang_cols),
        detection_script_table=metrics_to_table(detection_script_metrics, det_lang_cols),
        detection_type_table=metrics_to_table(detection_type_metrics, ["Type", "TP", "FN", "Recall"]),
        detection_lookalike_table=metrics_to_table(detection_lookalike_metrics, ["Type", "FP", "TN", "FPR"]),
        recognition_model_table=metrics_to_table(recognition_model_metrics, det_model_cols),
        recognition_lang_table=metrics_to_table(recognition_lang_metrics, det_lang_cols),
        recognition_script_table=metrics_to_table(recognition_script_metrics, det_lang_cols),
        f1_chart_data=json.dumps(f1_chart_data),
        recall_lang_chart_data=json.dumps(recall_lang_chart_data),
    )
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML report saved to {output_path}")