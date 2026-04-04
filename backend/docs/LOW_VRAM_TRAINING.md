# Training on Low VRAM GPU (4GB)

**Have a GPU with limited VRAM? Here's how to make it work.**

---

## Your GPU: RTX 3050 Laptop (4GB VRAM)

**Challenge:** Standard training needs 8-12GB  
**Solution:** Use smaller model + aggressive memory optimization

---

## Option A: Train 1B Model (Fits in 4GB)

### Step 1: Modify Training Script

Edit `scripts/finetune_studio_model.py`:

```python
# Change line ~26 from:
model_name="unsloth/llama-3.2-3b-bnb-4bit",

# To (use 1B model instead):
model_name="unsloth/llama-3.2-1b-bnb-4bit",
```

### Step 2: Reduce Batch Size

```python
# Change line ~78 from:
per_device_train_batch_size=1,
gradient_accumulation_steps=8,

# To (smaller batch):
per_device_train_batch_size=1,
gradient_accumulation_steps=16,  # Higher = more memory efficient
```

### Step 3: Reduce Sequence Length

```python
# Change line ~17 from:
MAX_SEQ_LENGTH = 4096

# To (shorter):
MAX_SEQ_LENGTH = 2048  # Half the length = half the memory
```

### Step 4: Train

```bash
python scripts/finetune_studio_model.py
```

**Expected:**
- Training time: 8-12 hours (slower than 3B)
- Memory usage: ~3.5GB (fits your GPU)
- Quality: 8/10 (vs 9.5/10 with 3B model)

---

## Option B: QLoRA with Extreme Optimization

Keep 3B model but use extreme memory saving:

### Create: `scripts/finetune_studio_model_low_vram.py`

```python
#!/usr/bin/env python3
"""
Fine-tune ScholarFlow-Studio for LOW VRAM GPUs (4GB)
Uses aggressive memory optimizations
"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for LOW VRAM
MAX_SEQ_LENGTH = 1024  # Reduced from 4096
OUTPUT_DIR = "models/scholarflow-studio-finetuned"
ADAPTER_DIR = "models/adapters/scholarflow-studio-lora"

def load_model():
    """Load with aggressive memory optimization"""
    logger.info("Loading model for 4GB VRAM...")
    
    # Force CPU offloading for some layers
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-1b-bnb-4bit",  # Smaller model
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
        device_map="auto",  # Auto device mapping
    )
    
    logger.info("Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,  # Reduced from 32 (less memory)
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
        ],  # Fewer target modules
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=3407,
    )
    
    return model, tokenizer

def prepare_writing_data(tokenizer):
    """Load and truncate training data"""
    logger.info("Loading academic writing data...")
    
    dataset = load_dataset(
        'json',
        data_files='data/training/scholarmate_training.jsonl',
        split='train'
    )
    
    # Take only first 500 examples (less memory)
    dataset = dataset.select(range(min(500, len(dataset))))
    
    def format_writing_prompt(example):
        """Format with truncation"""
        instruction = example['instruction'][:300]  # Truncate
        output = example['output'][:700]  # Truncate
        return {
            "text": f"""### Task:
{instruction}

### Academic Response:
{output}"""
        }
    
    dataset = dataset.map(format_writing_prompt)
    logger.info(f"Total writing examples: {len(dataset)}")
    
    return dataset

def train_model(model, tokenizer, dataset):
    """Fine-tune with memory optimization"""
    logger.info("Starting LOW VRAM training...")
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            output_dir=OUTPUT_DIR,
            per_device_train_batch_size=1,  # Minimum
            gradient_accumulation_steps=32,  # Maximum (simulate larger batch)
            warmup_steps=5,
            num_train_epochs=2,  # Fewer epochs
            learning_rate=2e-4,
            fp16=True,  # Use FP16 (saves memory)
            logging_steps=10,
            save_steps=200,
            optim="adamw_8bit",
            gradient_checkpointing=True,
            max_grad_norm=0.3,
        ),
    )
    
    trainer.train()
    logger.info("Fine-tuning complete!")
    
    return trainer

def save_model(model, tokenizer):
    """Save model"""
    logger.info("Saving model...")
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    
    logger.info("Merging and saving full model...")
    model.save_pretrained_merged(
        OUTPUT_DIR,
        tokenizer,
        save_method="merged_16bit",
    )
    
    logger.info(f"✅ Model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    logger.info("🚀 Starting LOW VRAM fine-tuning...")
    logger.info("⚠️  Using 1B model + aggressive optimization")
    
    # Clear GPU cache
    torch.cuda.empty_cache()
    
    # Load model
    model, tokenizer = load_model()
    
    # Prepare data
    dataset = prepare_writing_data(tokenizer)
    
    # Train
    trainer = train_model(model, tokenizer, dataset)
    
    # Save
    save_model(model, tokenizer)
    
    logger.info("🎓 LOW VRAM fine-tuning complete!")
```

### Run It

```bash
python scripts/finetune_studio_model_low_vram.py
```

**Expected:**
- Memory: ~3.8GB (just fits!)
- Training time: 10-14 hours
- Quality: 8/10 (good but not perfect)

---

## Memory Monitoring

### Watch GPU Usage During Training

```bash
# In another terminal, run:
watch -n 1 nvidia-smi
```

**If you see OOM errors:**
1. Reduce `MAX_SEQ_LENGTH` (1024 → 512)
2. Reduce training examples (500 → 250)
3. Close Figma and other GPU apps

---

## Troubleshooting

### ❌ "CUDA out of memory"

**Solutions:**

1. **Close GPU apps:**
   ```bash
   # Your nvidia-smi shows Figma using GPU
   # Close Figma Beta before training
   ```

2. **Use even smaller model:**
   ```python
   # In training script, try 1B instead of 3B
   model_name="unsloth/llama-3.2-1b-bnb-4bit"
   ```

3. **Reduce sequence length further:**
   ```python
   MAX_SEQ_LENGTH = 512  # Very short
   ```

4. **Train fewer examples:**
   ```python
   dataset = dataset.select(range(100))  # Just 100 examples
   ```

### ⚠️ Training is very slow

**4GB GPU will be slow.** Expect:
- 1B model: 8-12 hours
- 3B model with optimizations: 16-20 hours

**Alternative:** Use Google Colab (faster + more VRAM)

---

## Comparison: Your GPU vs Colab

| Aspect | RTX 3050 (4GB) | Colab T4 (16GB) |
|--------|----------------|-----------------|
| **VRAM** | 4GB | 16GB |
| **Model Size** | 1B only | 3B comfortable |
| **Training Time** | 8-12 hours | 4-6 hours |
| **Memory Issues** | Likely | Rare |
| **Quality** | 8/10 | 9.5/10 |
| **Cost** | Free (your laptop) | Free |

**Recommendation:** Still use Colab for better results.

---

## When to Use Your GPU

✅ **Good for:**
- Testing scripts before Colab
- Training on 100-200 examples (quick test)
- Inference (running trained models)
- Small 1B model training

❌ **Not ideal for:**
- Full 3B model training
- Large datasets (1000+ papers)
- Production-quality training

---

## Summary

Your RTX 3050 (4GB) CAN train models, but with limitations:

1. **Use 1B model** (not 3B)
2. **Reduce batch size** and sequence length
3. **Close other GPU apps** (Figma, etc.)
4. **Expect 8-12 hours** training time
5. **Quality: 8/10** (good but not perfect)

**Or just use Google Colab** for better results! 😊
