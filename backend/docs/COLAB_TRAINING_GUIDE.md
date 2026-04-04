# Training on Google Colab (Free GPU)

**No local GPU? No problem!** Google Colab provides free GPU access.

---

## Quick Setup

### Step 1: Open Google Colab

1. Go to: https://colab.research.google.com/
2. Click **New Notebook**
3. Enable GPU: `Runtime` → `Change runtime type` → `T4 GPU` → `Save`

---

### Step 2: Upload Training Scripts

**Create a new cell and run:**

```python
# Install dependencies
!pip install -q unsloth datasets transformers trl arxiv PyPDF2

# Clone your repo (or upload scripts manually)
from google.colab import files
import os

# Option A: Upload scripts directly
print("Upload your training scripts:")
uploaded = files.upload()  # Upload finetune_studio_model.py

# Option B: Clone from GitHub (if you have a repo)
# !git clone https://github.com/yourusername/scholarflow.git
# %cd scholarflow/backend
```

---

### Step 3: Collect Training Data

```python
# Download and run data collection
!python scripts/collect_training_data.py

# This will:
# - Download 200 papers from ArXiv
# - Extract sections (intro, methods, results, etc.)
# - Create 2,000 training examples
# - Save to data/training/scholarmate_training.jsonl
```

**Time: 2-3 hours**

---

### Step 4: Fine-Tune Model

```python
# Run fine-tuning
!python scripts/finetune_studio_model.py

# This will:
# - Load Llama 3.2 (3B) with 4-bit quantization
# - Add LoRA adapters
# - Train on your data
# - Save to models/scholarflow-studio-finetuned/
```

**Time: 3-6 hours on T4 GPU (free tier)**

---

### Step 5: Download Trained Model

```python
# Zip the trained model
!zip -r scholarflow-studio-finetuned.zip models/scholarflow-studio-finetuned/

# Download to your computer
from google.colab import files
files.download('scholarflow-studio-finetuned.zip')
```

---

### Step 6: Use on Your Local Machine

**Back on your Windows machine:**

```bash
# Extract the model
unzip scholarflow-studio-finetuned.zip

# Create Ollama model from the trained adapter
ollama create scholarflow-studio -f models/ScholarFlow-Studio-FineTuned.Modelfile
```

---

## Complete Colab Notebook Script

**Copy-paste this entire script into a Colab cell:**

```python
# ============================================
# ScholarFlow Training on Google Colab
# ============================================

print("🚀 Starting ScholarFlow training on Google Colab...")

# 1. Check GPU
import torch
print(f"✓ GPU Available: {torch.cuda.is_available()}")
print(f"✓ GPU Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

# 2. Install dependencies
print("\n📦 Installing dependencies...")
!pip install -q unsloth datasets transformers trl arxiv PyPDF2 bitsandbytes

# 3. Create directory structure
import os
os.makedirs("data/training", exist_ok=True)
os.makedirs("data/papers/pdfs", exist_ok=True)
os.makedirs("models/scholarflow-studio-finetuned", exist_ok=True)
os.makedirs("models/adapters", exist_ok=True)

# 4. Upload training scripts
print("\n📤 Upload your training scripts:")
print("   - collect_training_data.py")
print("   - finetune_studio_model.py")
from google.colab import files
uploaded = files.upload()

# Save uploaded files
for filename, content in uploaded.items():
    with open(filename, 'wb') as f:
        f.write(content)
    print(f"✓ Saved: {filename}")

# 5. Collect training data
print("\n📚 Collecting training data (2-3 hours)...")
!python collect_training_data.py

# 6. Fine-tune model
print("\n🎓 Fine-tuning model (3-6 hours)...")
!python finetune_studio_model.py

# 7. Zip and download
print("\n📦 Packaging trained model...")
!zip -r scholarflow-studio-finetuned.zip models/scholarflow-studio-finetuned/
!zip -r training-data.zip data/training/

print("\n✅ Training complete!")
print("📥 Downloading files...")
files.download('scholarflow-studio-finetuned.zip')
files.download('training-data.zip')

print("\n🎉 Done! Transfer files to your local machine.")
```

---

## Colab Tips

### Free Tier Limits

- **12-hour session limit** - Your notebook disconnects after 12 hours
- **Solution:** Save checkpoints! The training script saves every 100 steps
- If disconnected, re-upload and resume from checkpoint

### Speed Up Training

```python
# In finetune_studio_model.py, reduce batch size for faster (but less optimal) training:
per_device_train_batch_size=1,  # Smaller = faster
num_train_epochs=2,  # Fewer epochs = faster
```

### Monitor Progress

```python
# Add to see training progress
!pip install tensorboard
%load_ext tensorboard
%tensorboard --logdir models/scholarflow-studio-finetuned/
```

---

## Alternative: Colab Pro

**If training is too slow on free tier:**

- **Colab Pro:** $10/month
  - Faster GPUs (A100, V100)
  - 24-hour sessions
  - Training time: 1-2 hours

- **Worth it?** Yes, if training multiple models

---

## Troubleshooting

### "Runtime disconnected"
- Colab free tier has session limits
- Save checkpoints frequently
- Resume from last checkpoint

### "Out of memory"
```python
# Reduce batch size in training script:
per_device_train_batch_size=1
gradient_accumulation_steps=8
```

### "GPU not available"
- Go to: Runtime → Change runtime type
- Select: T4 GPU
- Click: Save

### "Training too slow"
- Use fewer papers (200 → 100)
- Reduce epochs (3 → 2)
- Or upgrade to Colab Pro

---

## Summary

1. ✅ **Open Colab** - Free GPU access
2. ✅ **Upload scripts** - Your training files
3. ✅ **Run training** - 5-8 hours total
4. ✅ **Download model** - Transfer to local machine
5. ✅ **Load into Ollama** - Use on your system

**Cost: $0 (free tier) or $10/month (Pro)**

**No GPU on your local machine needed!**
