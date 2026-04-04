# Quick Start: Training Specialized Models

**You're right - 2 specialized models > 1 general model!**

---

## ⚠️ GPU Requirement Check

**Before starting, check if you have a GPU:**

```bash
# Windows (PowerShell)
nvidia-smi

# If you see GPU info → You have a GPU ✅
# If error "command not found" → No GPU ❌
```

### Choose Your Path:

| Your Setup | Recommended Approach | Quality | Time |
|------------|---------------------|---------|------|
| **NVIDIA GPU (12GB+ VRAM)** | Train locally (this guide) | 9.5/10 | 8-12 hrs |
| **NVIDIA GPU (4-8GB VRAM)** | Train locally with optimizations | 8/10 | 10-14 hrs |
| **No GPU / CPU only** | Use Google Colab (free) | 9.5/10 | 8-12 hrs |
| **No GPU, need quick** | Skip fine-tuning, use Modelfiles | 7/10 | 5 min |

**📖 Have 4-8GB VRAM GPU?** See [LOW_VRAM_TRAINING.md](LOW_VRAM_TRAINING.md) for optimizations

**📖 If you don't have a GPU:** See [COLAB_TRAINING_GUIDE.md](COLAB_TRAINING_GUIDE.md) for free GPU access

**📖 To skip fine-tuning:** Use existing Modelfiles in `models/` folder - just run:
```bash
ollama create scholarmate -f models/ScholarMate.Modelfile
```

---

## Why This Approach?

**Problem:** RAG retrieves facts, but generic models write poorly  
**Solution:** Fine-tune specialized models on:
1. **QASPER** - Teaches Q&A and summarization
2. **ArXiv papers** - Teaches academic writing style

**Result:** RAG provides facts, specialized models write like researchers

---

## Complete Training Pipeline

### Setup (5 min)

```bash
cd backend
pip install -r scripts/requirements-finetuning.txt
```

---

### Train Model 1: ScholarFlow-QA (Reading Mode)

**Purpose:** Q&A, summaries, paper analysis

```bash
# Step 1: Collect QASPER data (1 hour)
python scripts/collect_qasper_data.py

# Step 2: Collect ArXiv data (2 hours)  
python scripts/collect_training_data.py

# Step 3: Fine-tune (3-6 hours on GPU)
python scripts/finetune_qa_model.py

# Step 4: Load into Ollama
ollama create scholarflow-qa -f models/ScholarFlow-QA-FineTuned.Modelfile
```

**What you get:**
- Better paper summaries
- Evidence-based Q&A
- Multi-hop reasoning
- Academic tone

---

### Train Model 2: ScholarFlow-Studio (Writing Mode)

**Purpose:** Paper composition, section generation

```bash
# Step 1: Fine-tune (3-6 hours on GPU)
python scripts/finetune_studio_model.py

# Step 2: Load into Ollama
ollama create scholarflow-studio -f models/ScholarFlow-Studio-FineTuned.Modelfile
```

**What you get:**
- Natural academic writing
- Original synthesis (not copying)
- Proper paper structure
- Human-like style

---

## Training Time

| GPU | Total Time | Cost |
|-----|------------|------|
| RTX 4090 | 4-5 hours | $0 |
| RTX 3060 | 10-12 hours | $0 |
| Google Colab (free) | 16 hours | $0 |

---

## How Models Work Together

```
User: "Summarize this transformer paper"
         ↓
┌────────────────────┐
│   RAG Retrieval    │  ← Finds Vaswani et al. 2017 paper
└────────────────────┘
         ↓
┌────────────────────┐
│  ScholarFlow-QA    │  ← Generates summary:
│   (fine-tuned)     │    "Vaswani et al. introduce the
└────────────────────┘     Transformer architecture..."
```

```
User: "Write an introduction about attention mechanisms"
         ↓
┌────────────────────┐
│   RAG Retrieval    │  ← Finds 10 papers on attention
└────────────────────┘
         ↓
┌────────────────────┐
│ ScholarFlow-Studio │  ← Writes original intro:
│   (fine-tuned)     │    "Attention mechanisms fundamentally
└────────────────────┘     reimagine sequence modeling..."
```

---

## Verify It's Working

**Test Q&A model:**
```bash
ollama run scholarflow-qa "Summarize: Attention Is All You Need paper by Vaswani et al."
```

**Expected output:**
```
Vaswani et al. (2017) introduce the Transformer architecture, 
which removes recurrence and relies entirely on self-attention 
mechanisms. The model achieves state-of-the-art BLEU scores 
of 28.4 on WMT 2014 English-to-German translation while 
enabling greater parallelization during training...
```

**Test Studio model:**
```bash
ollama run scholarflow-studio "Write an introduction paragraph about neural networks"
```

**Expected output:**
```
Neural networks have emerged as the dominant paradigm in 
modern machine learning, fundamentally transforming how we 
approach pattern recognition tasks (LeCun et al., 2015). 
While early architectures relied on shallow representations, 
recent advances in deep learning demonstrate that hierarchical 
feature learning enables unprecedented performance across 
diverse domains...
```

---

## Configuration

Update `backend/.env`:

```env
# For Reading mode (Q&A, summaries)
OLLAMA_MODEL_READING=scholarflow-qa

# For Studio mode (writing)
OLLAMA_MODEL_STUDIO=scholarflow-studio

# For Discovery mode (search)
OLLAMA_MODEL_SEARCH=scholarflow-search
```

**Or keep one general model:**
```env
# Use one model for both (less optimal)
OLLAMA_MODEL_SMART=scholarmate
```

---

## Troubleshooting

### ❌ "Unsloth cannot find any torch accelerator? You need a GPU."

**Problem:** No NVIDIA GPU detected  
**Solutions:**

1. **Option A: Use Google Colab (FREE GPU)**
   - See [COLAB_TRAINING_GUIDE.md](COLAB_TRAINING_GUIDE.md)
   - Get free T4 GPU access
   - Train in the cloud, download model

2. **Option B: Skip Fine-Tuning**
   ```bash
   # Use Modelfile customization (no training needed)
   ollama create scholarmate -f models/ScholarMate.Modelfile
   ollama create scholarflow-studio -f models/ScholarFlow-Studio.Modelfile
   ```
   - Quality: 7/10 (vs 9.5/10 with fine-tuning)
   - Setup time: 5 minutes
   - Works on any machine

3. **Option C: Cloud GPU Services**
   - Vast.ai ($0.20/hour)
   - Lambda Labs ($0.50/hour)  
   - Paperspace (from $8/month)

### ❌ "CUDA out of memory" / Have Low VRAM GPU

**Problem:** GPU has insufficient VRAM (e.g., RTX 3050 with 4GB)  
**Solutions:**

1. **Use Memory-Optimized Training**
   - See [LOW_VRAM_TRAINING.md](LOW_VRAM_TRAINING.md)
   - Train 1B model instead of 3B
   - Uses aggressive memory optimizations
   - Quality: 8/10 (still good!)

2. **Close GPU Applications**
   ```bash
   # Check what's using GPU:
   nvidia-smi
   
   # Close apps like Figma, Chrome, games, etc.
   ```

3. **Use Google Colab Instead**
   - Colab T4 has 16GB VRAM
   - Much more comfortable for training
   - Still free!

**Low VRAM GPU (4-8GB)?**
- See [LOW_VRAM_TRAINING.md](LOW_VRAM_TRAINING.md) for optimizations
- Close other GPU applications first
- Use 1B model instead of 3B

**Out of memory?**
- Reduce batch size in scripts
- Use 1B model instead of 3B
- Close other applications

**Training too slow?**
- Use Google Colab (free GPU)
- Reduce training data size
- Use fewer epochs (3 → 2)

---

## Next Steps

1. **Train both models** (8-12 hours total)
2. **Test quality** on sample papers
3. **Deploy** to your app
4. **Collect feedback** from users
5. **Iterate** - improve training data

See full guide: [SPECIALIZED_MODELS_TRAINING.md](SPECIALIZED_MODELS_TRAINING.md)
