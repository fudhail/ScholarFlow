#!/usr/bin/env python3
"""
Collect QASPER dataset for fine-tuning Q&A model
QASPER: Question Answering on Scientific Papers
Dataset: https://huggingface.co/datasets/allenai/qasper
"""
from datasets import load_dataset
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/training")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_qasper_dataset():
    """Load QASPER from HuggingFace"""
    logger.info("Loading QASPER dataset...")
    dataset = load_dataset("allenai/qasper")
    return dataset

def format_qasper_for_training(dataset):
    """
    Convert QASPER to instruction-following format
    QASPER has: paper context + questions + answers
    """
    training_data = []
    
    for split in ['train', 'validation']:
        logger.info(f"Processing {split} split...")
        
        for example in dataset[split]:
            title = example['title']
            abstract = example['abstract']
            full_text = example['full_text']
            
            # Create context from paper
            paper_context = f"Title: {title}\n\nAbstract: {abstract}"
            
            # Process each Q&A pair
            qas = example['qas']
            for qa in qas:
                question = qa['question']
                
                # Get answer (QASPER has extractive and abstractive)
                answers = qa['answers']
                if answers and len(answers) > 0:
                    answer = answers[0]['answer']  # Use first annotator's answer
                    
                    if answer and answer.get('free_form_answer'):
                        answer_text = answer['free_form_answer']
                        
                        # Create training example
                        training_data.append({
                            "instruction": f"Based on the following research paper, answer the question.\n\nPaper:\n{paper_context}\n\nQuestion: {question}",
                            "output": answer_text
                        })
    
    logger.info(f"Created {len(training_data)} Q&A training examples")
    return training_data

def create_summary_examples(dataset):
    """Create summarization examples from QASPER papers"""
    summary_data = []
    
    for split in ['train']:
        for example in dataset[split]:
            title = example['title']
            abstract = example['abstract']
            
            # Create summarization task
            summary_data.append({
                "instruction": f"Summarize the key contributions of this research paper:\n\nTitle: {title}\n\nAbstract: {abstract}",
                "output": f"This paper presents {title}. {abstract[:300]}..."
            })
    
    logger.info(f"Created {len(summary_data)} summarization examples")
    return summary_data

def save_training_data(data, filename):
    """Save in JSONL format"""
    output_path = OUTPUT_DIR / filename
    
    with output_path.open('w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
    
    logger.info(f"✅ Saved to {output_path}")

if __name__ == "__main__":
    logger.info("🚀 Starting QASPER data collection...")
    
    # Load dataset
    dataset = load_qasper_dataset()
    
    # Create Q&A training examples
    qa_data = format_qasper_for_training(dataset)
    save_training_data(qa_data, "qasper_qa_training.jsonl")
    
    # Create summary examples
    summary_data = create_summary_examples(dataset)
    save_training_data(summary_data, "qasper_summary_training.jsonl")
    
    logger.info(f"🎓 Total examples: {len(qa_data) + len(summary_data)}")
    logger.info("Next step: python scripts/finetune_qa_model.py")
