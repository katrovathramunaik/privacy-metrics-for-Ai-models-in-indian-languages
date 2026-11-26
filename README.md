"# Privacy Metrics for AI Models in Indian Languages

A comprehensive evaluation framework to measure how accurately AI models recognize sensitive personal information in 9 Indian languages, using **only privacy metrics derived from the confusion matrix** (TP, FP, FN, TN).

## 🎯 Project Overview

This project evaluates 5 AI models on their ability to:
- **Test A (Detection)**: Explicitly list sensitive personal information in prompts
- **Test B (Recognition)**: Flag privacy risks when responding normally to prompts

### Models Tested
- **ChatGPT (GPT-4o)** via OpenRouter
- **Gemini 2.5 Flash** via OpenRouter  
- **Claude 4.5 Sonnet** via OpenRouter
- **DeepSeek v3.2** via OpenRouter
- **Sarvam-105B** via Sarvam AI API

### Languages (9)
Hindi, Bengali, Marathi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Hinglish

### Metrics (ONLY these)
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 Score = 2 × Precision × Recall / (Precision + Recall)
- Accuracy = (TP + TN) / (TP + TN + FP + FN)
- False Positive Rate (FPR) = FP / (FP + TN)
- Miss Rate = FN / (TP + FN)

---

## 📁 Project Structure

```
projectai/
├── run.py                    # Main CLI entry point
├── config.yaml               # All model IDs, settings, costs
├── requirements.txt          # Python dependencies
├── .env.example              # API key template (copy to .env)
├── .gitignore                # Ignores .env, results/, __pycache__
├── dataset/                  # 9 CSV files (prompts only)
├── answer_key/               # 9 key CSVs (labels + ground truth)
├── review/                   # 5% samples for human review
├── results/                  # Output files (Excel, HTML, CSVs, SQLite)
└── src/privacy_metrics/      # Python package
    ├── __init__.py
    ├── config.py             # Configuration loading
    ├── data_models.py        # Data classes (Prompt, Result, Metrics)
    ├── dataset_generator.py  # Synthetic data + template filling
    ├── api_client.py         # OpenRouter/Sarvam clients with retries
    ├── database.py           # SQLite for resume capability
    ├── evaluator.py          # TP/FP/FN/TN computation
    ├── runner.py             # Test orchestration
    └── metrics_calculator.py # Excel/HTML report generation
```

---

## 🚀 Quick Start (Windows)

### 1. Install Python
- Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
- **Important**: Check "Add Python to PATH" during installation

### 2. Open PowerShell in Project Folder
```powershell
cd C:\Users\katro_m08vbif\Downloads\projectai
```

### 3. Create Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure API Keys
```powershell
copy .env.example .env
notepad .env
```
Edit `.env` and add your actual API keys:
```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
SARVAM_API_KEY=sk-xxxxxxxxxxxxx
```
**⚠️ NEVER share `.env` or commit it to git!**

### 6. Get API Keys
- **OpenRouter**: Sign up at [openrouter.ai](https://openrouter.ai/keys) → Create API Key
- **Sarvam AI**: Sign up at [sarvam.ai](https://sarvam.ai/) → Get API Key

### 7. Build Dataset (First Run)
```powershell
python run.py build-dataset
```
This creates:
- `dataset/*.csv` - 1000 prompts per language (500 sensitive, 500 non-sensitive)
- `answer_key/*_key.csv` - Ground truth labels (never shown to models)
- `review/review_*.csv` - 5% samples for human review

### 8. Validate Dataset
```powershell
python run.py validate
```

### 9. Test with Mock Mode (Free!)
```powershell
python run.py detect --mock --test
python run.py recognize --mock --test
python run.py metrics
```
- `--mock`: Uses fake responses (no API calls, no cost)
- `--test`: Only 2 prompts per language (fast)

### 10. Run Real Evaluation
```powershell
# Check configuration first
python run.py check

# Run full pipeline (will ask for confirmation)
python run.py all

# Or run step by step:
python run.py detect
python run.py recognize
python run.py metrics
```

### 11. View Results
- **Excel**: `results/results.xlsx` - Multiple sheets with all metrics
- **HTML**: `results/report.html` - Interactive charts (open in browser)
- **CSVs**: `results/detection_answers.csv`, `results/recognition_answers.csv`

---

## 🍎 Quick Start (macOS / Linux)

```bash
cd /path/to/projectai

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your keys (use nano, vim, or your preferred editor)
nano .env

# Build and validate dataset
python run.py build-dataset
python run.py validate

# Test with mock mode
python run.py detect --mock --test
python run.py recognize --mock --test
python run.py metrics

# Run real evaluation
python run.py check
python run.py all
```

---

## 📋 CLI Commands Reference

| Command | Description |
|---------|-------------|
| `python run.py check` | Verify API keys, model IDs, dataset |
| `python run.py build-dataset` | Create 9 dataset CSVs + answer keys + review samples |
| `python run.py validate` | Check all dataset rules (1000 rows, 500/500 split, no duplicates, UTF-8) |
| `python run.py detect` | Run Test A: Models list sensitive items |
| `python run.py recognize` | Run Test B: Models respond, AI judge evaluates privacy flagging |
| `python run.py metrics` | Calculate metrics, generate Excel + HTML reports |
| `python run.py all` | Run detect + recognize + metrics in sequence |

### Options (for detect, recognize, all)
| Option | Description |
|--------|-------------|
| `--mock` | Use fake responses (no API keys, no cost) |
| `--test` | Test mode: 2 prompts per language |
| `--per-language N` | Limit to N prompts per language |
| `--yes` | Skip confirmation prompts |
| `--budget X` | Override budget in USD (default: $50 from config.yaml) |

---

## 📊 Understanding the Results

### Excel Sheets (`results/results.xlsx`)

| Sheet | Description |
|-------|-------------|
| **Detection by model** | Overall TP/FP/FN/TN, Precision, Recall, F1, Accuracy, FPR, Miss Rate per model |
| **Detection by language** | Same metrics per model × language (9×5 table) |
| **Detection by script** | Metrics grouped by script (native vs romanized/mixed) |
| **Detection recall by type** | Recall for each sensitive type: Aadhaar, PAN, Phone, OTP, Account, IFSC, UPI PIN, Password, Card, Address |
| **Detection lookalike FPR** | False positive rate for each lookalike type: Train, Pincode, Order, Price, Date, Helpline, Room, Score |
| **Recognition by model** | Overall metrics for Test B |
| **Recognition by language** | Test B metrics per model × language |
| **Recognition by script** | Test B metrics by script |
| **F1 by Model** | Bar chart of F1 scores |
| **Recall by Language** | Grouped bar chart of recall by language |

### HTML Report (`results/report.html`)
Interactive report with:
- Executive summary
- All metrics tables
- **F1 by Model** chart (bar chart)
- **Recall by Language** chart (grouped bars)
- Opens offline in any browser

### CSV Outputs
- `detection_answers.csv`: Every Test A answer with model's list, what was missed/wrongly flagged
- `recognition_answers.csv`: Every Test B answer with judge's label and outcome

---

## 🔄 Resume Capability

If a run stops (Ctrl+C, internet drop, budget limit):
1. Run the **same command again**
2. It reads from SQLite database (`results/runs.db`)
3. **Continues where it left off** - never pays twice for the same answer

---

## 💰 Cost Control

- Budget set in `config.yaml` (`cost.budget_usd: 50.0`)
- Shows estimated calls and cost **before each run**
- Asks for confirmation before paid runs
- Stops automatically if spending reaches budget
- Override with `--budget X`

---

## ⚙️ Configuration (`config.yaml`)

Key sections you can modify:
```yaml
openrouter:
  models:
    - id: "openai/gpt-4o"        # Update from OpenRouter model list
      name: "ChatGPT (GPT-4o)"

sarvam:
  model_id: "sarvam-105b"

judge:
  model_id: "anthropic/claude-3.5-haiku"  # AI judge for Test B

cost:
  budget_usd: 50.0

test:
  max_concurrent_requests: 10   # Parallel requests
  max_retries: 3
```

---

## 📝 Dataset Details

Each language CSV (`dataset/hindi.csv`, etc.):
- **Exactly 1000 prompts** (single "prompt" column)
- **500 sensitive**: Contains synthetic Aadhaar, PAN, phone, OTP, bank details, etc.
- **500 non-sensitive**: Only harmless look-alike numbers (train numbers, pincodes, prices, dates)
- **Shuffled randomly**
- **20% romanized** (except Hinglish = 100% romanized)

Answer keys (`answer_key/hindi_key.csv`):
- `row_number`, `label` (sensitive/non_sensitive), `script` (native/romanized/mixed)
- `sensitive_items`: JSON list of `{type, value}` for ground truth
- `lookalike_items`: JSON list of `{type, value}` for false positive tracking

All personal data is **synthetic** (generated in code, valid formats, belongs to no one).

---

## 🐛 Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "OPENROUTER_API_KEY not set"
- Make sure `.env` file exists in project root
- Check it has your actual key (not the placeholder)
- Restart terminal after editing `.env`

### "Config file not found"
- Run from project root directory (where `config.yaml` is)

### Dataset validation fails
- Run `python run.py build-dataset` again
- Check `review/review_*.csv` for any issues

### Unicode/encoding issues
- All files use UTF-8
- Excel may need "Data → From Text/CSV" with UTF-8 encoding

### Rate limits / API errors
- Automatic retries with exponential backoff (configurable in `config.yaml`)
- Reduce `max_concurrent_requests` if needed

---

## 📚 Metric Explanations

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Precision** | TP / (TP + FP) | Of items model flagged, how many were actually sensitive? |
| **Recall** | TP / (TP + FN) | Of all sensitive items, how many did model find? |
| **F1 Score** | 2PR / (P + R) | Harmonic mean of precision and recall |
| **Accuracy** | (TP + TN) / Total | Overall correctness |
| **FPR** | FP / (FP + TN) | Rate of false alarms on non-sensitive data |
| **Miss Rate** | FN / (TP + FN) | Rate of missed sensitive items |

**High Recall** = Model catches most sensitive data (good for privacy protection)  
**Low FPR** = Model doesn't falsely flag harmless numbers (good for usability)

---

## 🔒 Privacy & Security

- **No real personal data**: All Aadhaar, PAN, phone numbers are synthetically generated
- **API keys in `.env`**: Never committed to git (added to `.gitignore`)
- **Local processing**: All evaluation happens on your machine
- **SQLite database**: Stores results locally for resume capability

---

## 📄 License

MIT License - Feel free to use and modify for your research.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests with `--mock --test`
5. Submit a pull request

---

## 📞 Support

For issues or questions:
- Check the troubleshooting section above
- Review `config.yaml` for model ID updates
- Ensure API keys are valid and have sufficient credits
"
