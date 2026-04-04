#!/usr/bin/env python3
"""
Fine-tune ScholarFlow-Studio for RTX 3050 (4GB VRAM)
EXTREME optimization to fit 3B model in 4GB
"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# EXTREME optimization for 3B in 4GB VRAM
MAX_SEQ_LENGTH = 512  # Very short sequences
OUTPUT_DIR = "models/scholarflow-studio-finetuned"
ADAPTER_DIR = "models/adapters/scholarflow-studio-lora"

# Enable memory optimizations
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

def load_model():
    """Load 3B model with EXTREME 4GB VRAM optimizations"""
    logger.info("⚠️  Loading 3B model with EXTREME optimizations for 4GB VRAM...")
    logger.info("⚠️  This is pushing the limits - close ALL other GPU apps!")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-3b-bnb-4bit",  # 3B model
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
        device_map="auto",
    )
    
    logger.info("Adding minimal LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,  # VERY low rank to save memory
        target_modules=[
            "q_proj", "v_proj",  # Only 2 modules instead of 4+
        ],
        lora_alpha=16,
        lora_dropout=0,  # No dropout to save memory
        bias="none",
        use_gradient_checkpointing=True,
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )
    
    return model, tokenizer

def prepare_writing_data(tokenizer):
    """Load training data with AGGRESSIVE truncation for 4GB"""
    logger.info("Loading academic writing data...")
    
    dataset = load_dataset(
        'json',
        data_files='data/training/scholarmate_training.jsonl',
        split='train'
    )
    
    # Limit to 200 examples for memory efficiency
    dataset = dataset.select(range(min(200, len(dataset))))
    
    def format_writing_prompt(example):
        """Format with VERY short sequences for 4GB"""
        instruction = example['instruction'][:250]  # Very short
        output = example['output'][:750]  # Very short
        return {
            "text": f"""### Task:
{instruction}

### Academic Response:
{output}"""
        }
    
    dataset = dataset.map(format_writing_prompt)
    logger.info(f"Training on {len(dataset)} examples (truncated for 4GB)")
    
    return dataset

def train_model(model, tokenizer, dataset):
    """Fine-tune with EXTREME memory optimization for 3B in 4GB"""
    logger.info("Starting fine-tuning (EXTREME 4GB optimization)...")
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            output_dir=OUTPUT_DIR,
            per_device_train_batch_size=1,  # Minimum batch size
            gradient_accumulation_steps=32,  # Very high to simulate batch
            warmup_steps=3,
            num_train_epochs=2,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=5,
            save_steps=50,
            optim="adamw_8bit",
            gradient_checkpointing=True,
            max_grad_norm=0.3,
            # Additional memory optimizations
            dataloader_num_workers=0,  # No parallel loading
            ddp_find_unused_parameters=False,
            save_total_limit=1,  # Keep only 1 checkpoint
        ),
    )
    
    trainer.train()
    logger.info("Fine-tuning complete!")
    
    return trainer

def save_model(model, tokenizer):
    """Save model and adapter"""
    logger.info("Saving LoRA adapter...")
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    
    logger.info("Merging and saving full model...")
    model.save_pretrained_merged(
        OUTPUT_DIR,
        tokenizer,
        save_method="merged_16bit",
    )
    
    logger.info(f"✅ Model s3B model with EXTREME memory optimizations")
    logger.info("⚠️  WARNING: This pushes 4GB to the limit!")
    logger.info("⚠️  CLOSE ALL OTHER GPU APPLICATIONS NOW!")
    
    # Clear GPU cache aggressively
    torch.cuda.empty_cache()
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    
    # Check GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"✓ GPU: {gpu_name}")
        logger.info(f"✓ VRAM: {gpu_memory:.1f} GB")
        
        # Warn if memory usage is already high
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        if allocated > 0.5:
            logger.warning(f"⚠️  GPU already using {allocated:.1f}GB - close other apps!")
    else:
        logger.error("❌ No GPU detected!")
        exit(1)
    
    try:
        # Load model
        model, tokenizer = load_model()
        
        # Check memory after loading
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        logger.info(f"📊 Memory after model load: {allocated:.2f}GB / {gpu_memory:.1f}GB")
        
        # Prepare data
        dataset = prepare_writing_data(tokenizer)
        
        # Train
        trainer = train_model(model, tokenizer, dataset)
        
        # Save
        save_model(model, tokenizer)
        
        logger.info("🎓 Training complete!")
        logger.info("Next: ollama create scholarflow-studio -f models/ScholarFlow-Studio-FineTuned.Modelfile")
        
    except RuntimeError as e:
        if "out of memory" in str(e):
            logger.error("❌ CUDA Out of Memory!")
            logger.error("💡 Try these solutions:")
            logger.error("   1. Close ALL other applications")
            logger.error("   2. Restart your computer")
            logger.error("   3. Or use 1B model: change line 28 to 'llama-3.2-1b-bnb-4bit'")
            logger.error("   4. Or use Google Colab (16GB free GPU)")
        else:
            raise e
    save_model(model, tokenizer)
    
    logger.info("🎓 Training complete!")
    logger.info("Next: ollama create scholarflow-studio -f models/ScholarFlow-Studio-FineTuned.Modelfile")
