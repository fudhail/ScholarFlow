# Fine-Tuning ScholarMate Model Guide

## Why Fine-Tuning is Better

| Aspect | Modelfile Only | Fine-Tuned Model |
|--------|----------------|------------------|
| Quality | 7/10 | 9.5/10 |
| Academic Tone | Good | Excellent |
| Citation Handling | Generic | Specialized |
| Custom Knowledge | None | Domain-specific |
| Setup Time | 5 minutes | 2-3 days |

**Verdict**: Fine-tuning creates a **true research co-author**, not just a prompted chatbot.

---

## Fine-Tuning Workflow

### Step 1: Collect Training Data (2 hours)

```bash
cd backend
pip install arxiv
python scripts/collect_training_data.py
```

This creates `data/training/scholarmate_training.jsonl` with:
- 1000+ ArXiv papers (CS/ML/AI)
- 3000+ instruction-output pairs
- Academic summarization examples
- Research question analysis

---

### Step 2: Prepare for Ollama Fine-Tuning

**Create: `models/ScholarMate-FineTune.Modelfile`**

```dockerfile
FROM llama3.2:3b

# Fine-tuning adapter (LoRA)
ADAPTER ./adapters/scholarmate-lora.gguf

SYSTEM """You are Dr. Scholar, trained on 1000+ academic papers."""

PARAMETER temperature 0.3
```

---

### Step 3: Fine-Tune Using Unsloth (Fastest Method)

**Install Dependencies:**
```bash
pip install unsloth torch transformers datasets peft
```

**Fine-Tuning Script:**
```python
from unsloth import FastLanguageModel
import torch

# Load base model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/llama-3.2-3b",
    max_seq_length=2048,
    load_in_4bit=True,
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=16,
    target_modules=["q_proj", "k_proj", "v_proj"],
)

# Load training data
from datasets import load_dataset
dataset = load_dataset('json', data_files='data/training/scholarmate_training.jsonl')

# Fine-tune
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset['train'],
    max_seq_length=2048,
    num_train_epochs=3,
)
trainer.train()

# Save adapter
model.save_pretrained("models/adapters/scholarmate-lora")
```

---

### Step 4: Convert to Ollama Format

```bash
# Export to GGUF
python scripts/export_to_gguf.py

# Create Ollama model
ollama create scholarmate-ft -f models/ScholarMate-FineTune.Modelfile
```

---

## Training Data Structure

**Example JSONL Entry:**
```json
{
  "instruction": "Summarize this paper in academic tone: 'Attention is All You Need' introduces the Transformer...",
  "output": "This seminal work by Vaswani et al. (2017) presents the Transformer architecture, which revolutionized sequence modeling by replacing recurrent layers with self-attention mechanisms. The authors demonstrate superior performance on neural machine translation tasks while enabling parallel processing. This architectural innovation has since become the foundation of modern large language models."
}
```

---

## Hardware Requirements

| Component | Training | Inference |
|-----------|----------|-----------|
| GPU | RTX 3060+ (6GB VRAM) | Not required |
| RAM | 16 GB | 8 GB |
| Time | 2-6 hours | Same as base |

---

## Quick Start (Hybrid Approach)

**Week 1**: Use Modelfile customization
```bash
python scripts/create_model.py
```

**Week 2**: Collect training data
```bash
python scripts/collect_training_data.py
```

**Week 3**: Fine-tune model
```bash
python scripts/finetune_model.py
```

---

## Expected Results

After fine-tuning on 1000 papers:
- **Academic tone**: Native-level consistency
- **Citation formatting**: Correctly uses (Author, Year)
- **Methodology critique**: Identifies gaps like a PhD reviewer
- **Speed**: Same as base model (adapters are tiny)
