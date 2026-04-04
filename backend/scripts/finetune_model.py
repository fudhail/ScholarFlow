#!/usr/bin/env python3
"""
Fine-tune Llama 3.2 for ScholarMate using Unsloth
Optimized for consumer GPUs (RTX 3060+)
"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MAX_SEQ_LENGTH = 2048
TRAINING_DATA = "data/training/scholarmate_training.jsonl"
OUTPUT_DIR = "models/scholarmate-finetuned"
ADAPTER_DIR = "models/adapters/scholarmate-lora"

def load_model():
    """Load base Llama 3.2 model with 4-bit quantization"""
    logger.info("Loading base model...")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-3b-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )
    
    logger.info("Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,  # LoRA rank
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=3407,
    )
    
    return model, tokenizer

def prepare_data(tokenizer):
    """Load and format training data"""
    logger.info("Loading training data...")
    
    dataset = load_dataset('json', data_files=TRAINING_DATA, split='train')
    
    def format_prompt(example):
        return {
            "text": f"""### Instruction:
{example['instruction']}

### Response:
{example['output']}"""
        }
    
    dataset = dataset.map(format_prompt)
    return dataset

def train_model(model, tokenizer, dataset):
    """Fine-tune the model"""
    logger.info("Starting fine-tuning...")
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            output_dir=OUTPUT_DIR,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            num_train_epochs=3,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            save_steps=100,
            optim="adamw_8bit",
        ),
    )
    
    trainer.train()
    logger.info("Fine-tuning complete!")
    
    return trainer

def save_model(model, tokenizer):
    """Save LoRA adapter and merged model"""
    logger.info("Saving LoRA adapter...")
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
    logger.info("🚀 Starting ScholarMate fine-tuning...")
    
    # Load model
    model, tokenizer = load_model()
    
    # Prepare data
    dataset = prepare_data(tokenizer)
    logger.info(f"Loaded {len(dataset)} training examples")
    
    # Train
    trainer = train_model(model, tokenizer, dataset)
    
    # Save
    save_model(model, tokenizer)
    
    logger.info("🎓 ScholarMate fine-tuning complete!")
