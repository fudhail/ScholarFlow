#!/usr/bin/env python3
"""
Fine-tune ScholarFlow-QA model for Reading mode
Dataset: QASPER + ArXiv (Q&A and summarization)
"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset, concatenate_datasets
from trl import SFTTrainer
from transformers import TrainingArguments
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MAX_SEQ_LENGTH = 2048
OUTPUT_DIR = "models/scholarflow-qa-finetuned"
ADAPTER_DIR = "models/adapters/scholarflow-qa-lora"

def load_model():
    """Load Llama 3.2 for Q&A specialization"""
    logger.info("Loading base model for Q&A fine-tuning...")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-3b-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    
    logger.info("Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
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

def prepare_qa_data(tokenizer):
    """Load QASPER + ArXiv Q&A data"""
    logger.info("Loading Q&A training data...")
    
    # Load QASPER Q&A
    qasper_qa = load_dataset(
        'json', 
        data_files='data/training/qasper_qa_training.jsonl',
        split='train'
    )
    
    # Load QASPER summaries
    qasper_summary = load_dataset(
        'json',
        data_files='data/training/qasper_summary_training.jsonl',
        split='train'
    )
    
    # Load ArXiv data (from existing script)
    try:
        arxiv_data = load_dataset(
            'json',
            data_files='data/training/scholarmate_training.jsonl',
            split='train'
        )
    except:
        logger.warning("ArXiv data not found, using QASPER only")
        arxiv_data = None
    
    # Combine datasets
    if arxiv_data:
        dataset = concatenate_datasets([qasper_qa, qasper_summary, arxiv_data])
    else:
        dataset = concatenate_datasets([qasper_qa, qasper_summary])
    
    def format_prompt(example):
        return {
            "text": f"""### Instruction:
{example['instruction']}

### Response:
{example['output']}"""
        }
    
    dataset = dataset.map(format_prompt)
    logger.info(f"Total training examples: {len(dataset)}")
    
    return dataset

def train_model(model, tokenizer, dataset):
    """Fine-tune for Q&A"""
    logger.info("Starting Q&A fine-tuning...")
    
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
    """Save Q&A model"""
    logger.info("Saving Q&A model...")
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    
    logger.info("Merging and saving full model...")
    model.save_pretrained_merged(
        OUTPUT_DIR,
        tokenizer,
        save_method="merged_16bit",
    )
    
    logger.info(f"✅ Q&A model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    logger.info("🚀 Starting ScholarFlow-QA fine-tuning...")
    
    # Load model
    model, tokenizer = load_model()
    
    # Prepare data
    dataset = prepare_qa_data(tokenizer)
    
    # Train
    trainer = train_model(model, tokenizer, dataset)
    
    # Save
    save_model(model, tokenizer)
    
    logger.info("🎓 ScholarFlow-QA fine-tuning complete!")
    logger.info("Next: ollama create scholarflow-qa -f models/ScholarFlow-QA.Modelfile")
