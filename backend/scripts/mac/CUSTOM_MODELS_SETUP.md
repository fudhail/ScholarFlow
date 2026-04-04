# ScholarFlow — Custom Models Setup Guide

> Complete step-by-step guide to setting up, fine-tuning, and deploying ScholarFlow's custom Ollama models on **macOS (Apple Silicon)**.

---

## Table of Contents

- [Overview](#overview)
- [Model Inventory](#model-inventory)
- [Prerequisites](#prerequisites)
- [Phase 1: Quick Start — Prompt-Tuned Models](#phase-1-quick-start--prompt-tuned-models)
- [Phase 2: Collect Training Data](#phase-2-collect-training-data)
- [Phase 3: Fine-Tune on Apple Silicon (MLX)](#phase-3-fine-tune-on-apple-silicon-mlx)
- [Phase 4: Register Fine-Tuned Models](#phase-4-register-fine-tuned-models)
- [Phase 5: Verify & Benchmark](#phase-5-verify--benchmark)
- [Configuration Reference](#configuration-reference)
- [Modelfile Reference](#modelfile-reference)
- [Troubleshooting](#troubleshooting)
- [Alternative: Fine-Tuning on Cloud GPU](#alternative-fine-tuning-on-cloud-gpu)

---

## Overview

ScholarFlow uses **5 custom Ollama models**, each specialized for a different research task. They are built on top of Meta's **Llama 3.2** and enhanced through two methods:

1. **Prompt-Tuning (Quick)** — Custom system prompts + parameter tuning via Ollama `Modelfile`s. No training required. Works immediately.
2. **LoRA Fine-Tuning (Advanced)** — Additional training on academic papers from ArXiv using LoRA adapters. Produces higher-quality outputs for writing and Q&A tasks.

### Two Paths

```
┌──────────────────────────────────────────────────────────────┐
│  PATH A: Quick Start (5 minutes)                             │
│  → Just need Ollama + Modelfiles                             │
│  → Good results with prompt engineering                      │
│  → Run: bash scripts/mac/setup_models.sh                     │
├──────────────────────────────────────────────────────────────┤
│  PATH B: Full Fine-Tuning (2-4 hours)                        │
│  → Collect ArXiv training data                               │
│  → Fine-tune with MLX on Apple Silicon                       │
│  → Register fine-tuned adapters with Ollama                  │
│  → Significantly better academic writing quality             │
└──────────────────────────────────────────────────────────────┘
```

---

## Model Inventory

| Model Name | Base | Size | Purpose | Used By |
|---|---|---|---|---|
| `scholarmate` | Llama 3.2 3B | ~2.0GB | Primary research co-author — analysis, synthesis, chat | Supervisor, Router, RAG Response |
| `scholarmate-fast` | Llama 3.2 1B | ~1.3GB | Fast routing, intent classification, quick ranking | Router Node, Clarifier |
| `scholarflow-search` | Llama 3.2 1B | ~1.3GB | Paper relevance scoring (0.0–1.0) | Ranker Node |
| `scholarflow-studio` | Llama 3.2 3B | ~2.0GB | Original academic writing (anti-plagiarism) | Writer Node |
| `scholarmate-cot` | Llama 3.2 3B | ~2.0GB | Chain-of-thought reasoning with `<thinking>` tags | Optional for transparent reasoning |

### How They Map to the Agent System

```
User Query
    ↓
[Router] ← scholarmate-fast (1B, fast intent classification)
    ↓
[Search → Ranker] ← scholarflow-search (1B, paper scoring)
    ↓
[RAG Response] ← scholarmate (3B, synthesis + citations)
    ↓
[Writer] ← scholarflow-studio (3B, academic writing)
    ↓
[Reviewer] ← scholarmate (3B, critique + feedback)
```

---

## Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **Mac Chip** | M1 | M2 Pro / M3 Pro or higher |
| **Unified Memory** | 8GB | 16GB+ (for fine-tuning: 32GB+) |
| **Disk Space** | 10GB free | 30GB+ free (for training data + models) |

### Software Requirements

| Software | How to Install |
|---|---|
| **Homebrew** | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| **Ollama** | `brew install ollama` or download from [ollama.com/download/mac](https://ollama.com/download/mac) |
| **Python 3.10+** | `brew install python@3.11` |
| **Node.js 18+** | `brew install node` |
| **Git** | Pre-installed on macOS |

---

## Phase 1: Quick Start — Prompt-Tuned Models

This creates all 5 models using **Modelfiles only** (no training). Takes ~5 minutes.

### Step 1: Start Ollama

```bash
# Start the Ollama background service
ollama serve
# Or open the Ollama app from Applications
```

### Step 2: Run the Setup Script

```bash
cd backend
chmod +x scripts/mac/setup_models.sh
bash scripts/mac/setup_models.sh
```

This script will:
1. ✅ Check that Ollama is installed and running
2. ✅ Detect Apple Silicon vs Intel
3. ✅ Pull `llama3.2:1b` and `llama3.2:3b` base models
4. ✅ Create all 5 custom models from Modelfiles
5. ✅ Verify all models are registered
6. ✅ Run a smoke test

### Step 3: Verify

```bash
ollama list
```

Expected output:
```
NAME                    SIZE      MODIFIED
scholarmate:latest      2.0 GB    Just now
scholarmate-fast:latest 1.3 GB    Just now
scholarflow-search      1.3 GB    Just now
scholarflow-studio      2.0 GB    Just now
scholarmate-cot         2.0 GB    Just now
llama3.2:3b             2.0 GB    ...
llama3.2:1b             1.3 GB    ...
```

### Step 4: Quick Test

```bash
# Test the primary model
ollama run scholarmate "Summarize the attention mechanism in transformers in 3 sentences."

# Test the search model
ollama run scholarflow-search "Rate relevance 0.0-1.0: Paper 'BERT: Pre-training' to query 'attention in NLP'"

# Test the studio model
ollama run scholarflow-studio "Write a 3-sentence introduction about attention mechanisms."
```

**You can now start ScholarFlow!** The models are ready. Fine-tuning (Phase 2–4) is optional for improved quality.

---

## Phase 2: Collect Training Data

Fine-tuning requires academic paper data. The `collect_training_data.py` script downloads papers from ArXiv, extracts their sections (Introduction, Methods, Results, etc.), and creates instruction-following training examples.

### Step 1: Install Data Collection Dependencies

```bash
cd backend
pip3 install arxiv PyPDF2
```

### Step 2: Run Data Collection

```bash
python3 scripts/collect_training_data.py
```

**What this does:**
1. Fetches ~1000 paper metadata from ArXiv (AI, ML, NLP, CV categories)
2. Downloads full PDFs (~200 papers)
3. Extracts text and parses into sections
4. Creates ~2000+ training examples covering:
   - Introduction writing
   - Methodology writing
   - Results writing
   - Conclusion writing
   - Paper type identification
   - Research planning
   - Summarization
   - Related work writing

**Output:** `data/training/scholarmate_training.jsonl`

**Estimated time:** 15–30 minutes (depends on internet speed)

### Step 3: Verify Training Data

```bash
wc -l data/training/scholarmate_training.jsonl
# Expected: 1000-3000 lines

# Preview a few examples
head -3 data/training/scholarmate_training.jsonl | python3 -m json.tool
```

---

## Phase 3: Fine-Tune on Apple Silicon (MLX)

ScholarFlow uses **MLX** (Apple's ML framework) for native Apple Silicon fine-tuning. No CUDA or cloud GPU required.

### Step 1: Set Up Fine-Tuning Environment

```bash
chmod +x scripts/mac/setup_finetune_env.sh
bash scripts/mac/setup_finetune_env.sh
```

This installs `mlx`, `mlx-lm`, and other dependencies.

### Step 2: Fine-Tune the Studio Model (Academic Writing)

```bash
python3 scripts/mac/finetune_mlx.py --model studio
```

**What this does:**
1. Downloads `Llama-3.2-3B-Instruct-4bit` in MLX format
2. Converts training data to MLX chat format
3. Trains LoRA adapters (rank 32) on your Apple Silicon GPU
4. Fuses adapters into the base model
5. Exports for Ollama

| Setting | Value |
|---|---|
| Base model | Llama 3.2 3B (4-bit quantized) |
| LoRA rank | 32 (high for complex writing) |
| Max sequence length | 4096 tokens |
| Epochs | 3 |
| Training time | ~1-2 hours on M2 Pro |

### Step 3: Fine-Tune the QA Model (Reading Mode)

```bash
python3 scripts/mac/finetune_mlx.py --model qa
```

| Setting | Value |
|---|---|
| Base model | Llama 3.2 3B (4-bit quantized) |
| LoRA rank | 16 |
| Max sequence length | 2048 tokens |
| Epochs | 3 |
| Training time | ~45 min on M2 Pro |

### Step 4: Fine-Tune the Base Model (Optional)

```bash
python3 scripts/mac/finetune_mlx.py --model base
```

### Low-Memory Systems (8GB)

For Macs with 8GB unified memory, the script automatically reduces settings:
- Batch size → 1
- Max sequence length → 1024
- LoRA rank → 8

---

## Phase 4: Register Fine-Tuned Models

After fine-tuning, register the improved models with Ollama:

```bash
chmod +x scripts/mac/register_finetuned.sh
bash scripts/mac/register_finetuned.sh
```

This script:
1. Detects which models have fine-tuned adapters
2. Uses fine-tuned Modelfiles when adapters exist
3. Falls back to prompt-tuned Modelfiles otherwise
4. Re-registers all models with Ollama

---

## Phase 5: Verify & Benchmark

### Run the Benchmark

```bash
chmod +x scripts/mac/benchmark.sh
bash scripts/mac/benchmark.sh
```

This tests all models and reports response times. Expected results on Apple Silicon:

| Model | Expected Speed |
|---|---|
| `scholarmate-fast` (1B) | 0.3–0.8s |
| `scholarflow-search` (1B) | 0.3–0.8s |
| `scholarmate` (3B) | 1.0–3.0s |
| `scholarflow-studio` (3B) | 1.5–4.0s |

---

## Configuration Reference

All model configuration lives in `backend/app/core/config.py`:

```python
# Ollama Config
ollama_base_url: str = "http://localhost:11434"
ollama_model_fast: str = "llama3.2:1b"          # Fast routing/intent
ollama_model_smart: str = "scholarmate"          # Primary research tasks
ollama_model_search: str = "scholarflow-search"  # Paper relevance scoring
ollama_model_studio: str = "scholarflow-studio"  # Academic writing

# Hybrid Mode — which tasks use Ollama vs Gemini
use_ollama_for_chat: bool = True       # Chat → Ollama
use_ollama_for_writing: bool = True    # Writing → Ollama
use_ollama_for_ranking: bool = True    # Ranking → Ollama
use_gemini_for_vision: bool = True     # Vision → Gemini (always)

# Chain-of-Thought (optional)
enable_cot_reasoning: bool = False
show_thinking_to_user: bool = False
```

To use the CoT model, update your `.env`:
```env
OLLAMA_MODEL_SMART=scholarmate-cot
ENABLE_COT_REASONING=true
```

---

## Modelfile Reference

All Modelfiles are in `backend/models/`:

| File | Model | Base | Key Parameters |
|---|---|---|---|
| `ScholarMate.Modelfile` | `scholarmate` | llama3.2:3b | temp=0.35, ctx=4096, predict=2560 |
| `ScholarMate-Fast.Modelfile` | `scholarmate-fast` | llama3.2:1b | temp=0.7, ctx=4096, predict=1024 |
| `ScholarFlow-Search.Modelfile` | `scholarflow-search` | llama3.2:1b | temp=0.2, ctx=2048, predict=512 |
| `ScholarFlow-Studio.Modelfile` | `scholarflow-studio` | llama3.2:3b | temp=0.75, ctx=8192, predict=3072 |
| `ScholarMate-CoT.Modelfile` | `scholarmate-cot` | llama3.2:3b | temp=0.4, ctx=4096, predict=3072 |
| `ScholarFlow-Studio-FineTuned.Modelfile` | `scholarflow-studio` | llama3.2:3b + LoRA | temp=0.7, ctx=4096, predict=2048 |
| `ScholarFlow-QA-FineTuned.Modelfile` | `scholarflow-qa` | llama3.2:3b + LoRA | temp=0.3, ctx=4096, predict=1024 |

### Parameter Tuning Guide

| Parameter | Low (Search) | Medium (Chat) | High (Writing) |
|---|---|---|---|
| `temperature` | 0.2 | 0.35 | 0.75 |
| `top_p` | 0.85 | 0.9 | 0.92 |
| `top_k` | 30 | 50 | 50 |
| `repeat_penalty` | 1.05 | 1.1 | 1.18 |
| `num_predict` | 512 | 2560 | 3072 |
| `num_ctx` | 2048 | 4096 | 8192 |

---

## Troubleshooting

### Ollama won't start
```bash
# Kill existing processes and restart
pkill -f ollama
ollama serve
```

### Model creation fails
```bash
# Ensure you're in the right directory
cd backend/models
ollama create scholarmate -f ScholarMate.Modelfile

# If base model not found
ollama pull llama3.2:3b
```

### MLX fine-tuning OOM (Out of Memory)
- Close all other apps (Chrome, Docker, VS Code)
- Reduce batch size: edit `finetune_mlx.py` → `batch_size: 1`
- Reduce sequence length: `max_seq_length: 512`
- Use 1B model instead of 3B

### Model responds slowly
```bash
# Keep model warm in memory
export OLLAMA_KEEP_ALIVE=600  # 10 minutes

# Or set in Ollama config
echo 'OLLAMA_KEEP_ALIVE=600' >> ~/.ollama/envrc
```

### "Connection refused" errors
```bash
# Make sure Ollama is running
ollama serve &

# Check it's listening
curl http://localhost:11434/api/tags
```

---

## Alternative: Fine-Tuning on Cloud GPU

If you don't have Apple Silicon or need faster training:

### Google Colab (Free)

1. Upload `data/training/scholarmate_training.jsonl` to Google Drive
2. Open a Colab notebook with GPU runtime (T4 free, A100 Pro)
3. Install Unsloth:
   ```python
   !pip install unsloth transformers trl datasets
   ```
4. Run the existing Windows script (it works on Colab):
   ```python
   !python scripts/finetune_studio_model.py
   ```
5. Download the adapter files and copy to `backend/models/adapters/`

### Linux with NVIDIA GPU

The existing scripts in `backend/scripts/` work directly:
```bash
pip install unsloth transformers trl datasets
python3 scripts/finetune_model.py           # Base model
python3 scripts/finetune_studio_model.py    # Studio model
python3 scripts/finetune_qa_model.py        # QA model
```

---

## Script Index

All Mac scripts in `backend/scripts/mac/`:

| Script | Purpose | Run Time |
|---|---|---|
| `setup_models.sh` | Pull base models + create all custom models | ~5 min |
| `setup_finetune_env.sh` | Install MLX + fine-tuning dependencies | ~2 min |
| `finetune_mlx.py` | Fine-tune models on Apple Silicon | ~1-2 hrs |
| `register_finetuned.sh` | Register fine-tuned models with Ollama | ~1 min |
| `benchmark.sh` | Benchmark all model speeds | ~2 min |
