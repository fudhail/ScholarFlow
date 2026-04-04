#!/usr/bin/env python3
"""
Fine-tune ScholarFlow-Studio model for paper writing
Dataset: S2ORC + Academic papers from ArXiv (full-text)
Focus: Paper composition, section generation, academic writing
"""
import torch
from unsloth import FastLanguageModel
from datasets import Dataset, concatenate_datasets, load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MAX_SEQ_LENGTH = 4096  # Longer for paper generation
OUTPUT_DIR = "models/scholarflow-studio-finetuned"
ADAPTER_DIR = "models/adapters/scholarflow-studio-lora"

def load_model():
    """Load Llama 3.2 for paper writing specialization"""
    logger.info("Loading base model for writing fine-tuning...")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-3b-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    
    logger.info("Adding LoRA adapters for writing...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=32,  # Higher rank for complex writing
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=3407,
    )
    
    return model, tokenizer

def load_s2orc_abstracts(max_examples: int = 5000):
    """Stream a small subset of S2ORC abstracts for writing examples"""
    try:
        logger.info(f"Streaming up to {max_examples} S2ORC abstracts...")
        stream = load_dataset("allenai/s2orc", "metadata", split="train", streaming=True)
        buffer = []

        for example in stream:
            abstract = example.get("abstract")
            title = example.get("title")
            if not abstract or not title:
                continue

            buffer.append({
                "instruction": f"Write an academic abstract for the paper titled \"{title}\".",
                "output": abstract.strip(),
            })

            if len(buffer) >= max_examples:
                break

        if not buffer:
            logger.warning("No S2ORC abstracts loaded; continuing with ArXiv data only.")
            return None

        logger.info(f"Loaded {len(buffer)} S2ORC examples.")
        return Dataset.from_list(buffer)
    except Exception as exc:
        logger.warning(f"Skipping S2ORC dataset due to error: {exc}")
        return None

def prepare_writing_data(tokenizer):
    """Load academic writing dataset"""
    logger.info("Loading academic writing data...")
    
    arxiv_dataset = load_dataset(
        'json',
        data_files='data/training/scholarmate_training.jsonl',
        split='train'
    )
    arxiv_dataset = arxiv_dataset.select_columns(
        [col for col in arxiv_dataset.column_names if col in {"instruction", "output"}]
    )

    s2orc_dataset = load_s2orc_abstracts(max_examples=5000)
    datasets = [arxiv_dataset]
    if s2orc_dataset is not None and len(s2orc_dataset) > 0:
        datasets.append(s2orc_dataset)
        logger.info("Combining ArXiv and S2ORC datasets.")

    dataset = concatenate_datasets(datasets) if len(datasets) > 1 else datasets[0]
    
    def format_writing_prompt(example):
        """Format for paper writing tasks"""
        return {
            "text": f"""### Task:
{example['instruction']}

### Academic Response:
{example['output']}"""
        }
    
    dataset = dataset.map(format_writing_prompt)
    logger.info(f"Total writing examples: {len(dataset)}")
    
    return dataset

def train_model(model, tokenizer, dataset):
    """Fine-tune for academic writing"""
    logger.info("Starting writing fine-tuning...")
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            output_dir=OUTPUT_DIR,
            per_device_train_batch_size=1,  # Lower for longer sequences
            gradient_accumulation_steps=8,
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
    """Save Studio model"""
    logger.info("Saving Studio model...")
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    
    logger.info("Merging and saving full model...")
    model.save_pretrained_merged(
        OUTPUT_DIR,
        tokenizer,
        save_method="merged_16bit",
    )
    
    logger.info(f"✅ Studio model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    logger.info("🚀 Starting ScholarFlow-Studio fine-tuning...")
    
    # Load model
    model, tokenizer = load_model()
    
    # Prepare data
    dataset = prepare_writing_data(tokenizer)
    
    # Train
    trainer = train_model(model, tokenizer, dataset)
    
    # Save
    save_model(model, tokenizer)
    
    logger.info("🎓 ScholarFlow-Studio fine-tuning complete!")
    logger.info("Next: Update models/ScholarFlow-Studio.Modelfile with ADAPTER path")
