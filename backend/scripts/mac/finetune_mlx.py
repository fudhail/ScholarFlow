#!/usr/bin/env python3
"""
Fine-tune ScholarFlow models on Apple Silicon (M1/M2/M3/M4) using MLX
MLX is Apple's native ML framework — runs directly on Metal GPU
No CUDA required. Efficient unified memory usage.

Usage:
    python3 scripts/mac/finetune_mlx.py --model studio   # Academic writing model
    python3 scripts/mac/finetune_mlx.py --model qa        # Q&A model
    python3 scripts/mac/finetune_mlx.py --model base      # General research model
"""
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ──── Resolve paths relative to backend/ ────
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = BACKEND_DIR / "data" / "training"
OUTPUT_DIR = BACKEND_DIR / "models" / "mlx-finetuned"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ──── Model configs ────
MODEL_CONFIGS = {
    "base": {
        "name": "scholarmate",
        "base_model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "training_file": "scholarmate_training.jsonl",
        "output_dir": OUTPUT_DIR / "scholarmate",
        "num_epochs": 3,
        "batch_size": 4,
        "lora_rank": 16,
        "learning_rate": 1e-4,
        "max_seq_length": 2048,
        "description": "Primary research co-author (general academic tasks)",
    },
    "studio": {
        "name": "scholarflow-studio",
        "base_model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "training_file": "scholarmate_training.jsonl",
        "output_dir": OUTPUT_DIR / "scholarflow-studio",
        "num_epochs": 3,
        "batch_size": 2,  # Lower for longer sequences
        "lora_rank": 32,  # Higher rank for complex writing
        "learning_rate": 1e-4,
        "max_seq_length": 4096,
        "description": "Academic paper writing specialist",
    },
    "qa": {
        "name": "scholarflow-qa",
        "base_model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "training_file": "scholarmate_training.jsonl",
        "output_dir": OUTPUT_DIR / "scholarflow-qa",
        "num_epochs": 3,
        "batch_size": 4,
        "lora_rank": 16,
        "learning_rate": 2e-4,
        "max_seq_length": 2048,
        "description": "Paper Q&A and summarization specialist",
    },
}


def check_system():
    """Verify Apple Silicon and MLX availability."""
    import platform

    if platform.machine() != "arm64":
        logger.error("Apple Silicon (arm64) is required for MLX fine-tuning.")
        logger.error("Use scripts/finetune_model.py with CUDA on Linux/Windows instead.")
        sys.exit(1)

    try:
        import mlx  # noqa: F401
        import mlx_lm  # noqa: F401
        logger.info("✓ MLX and mlx-lm are available")
    except ImportError:
        logger.error("MLX not installed. Run: pip3 install mlx mlx-lm")
        sys.exit(1)

    import os
    mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    mem_gb = mem_bytes / (1024 ** 3)
    logger.info(f"✓ Unified memory: {mem_gb:.0f}GB")

    if mem_gb < 16:
        logger.warning("⚠ 16GB+ recommended for 3B fine-tuning. Using reduced settings.")

    return mem_gb


def prepare_training_data(config: dict) -> Path:
    """Convert JSONL training data into MLX-compatible chat format."""
    input_path = DATA_DIR / config["training_file"]
    if not input_path.exists():
        logger.error(f"Training data not found: {input_path}")
        logger.error("Run first: python3 scripts/collect_training_data.py")
        sys.exit(1)

    # MLX-LM expects {"messages": [{"role":"user","content":...},{"role":"assistant","content":...}]}
    output_path = config["output_dir"] / "train.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid_count = 0
    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            try:
                example = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            instruction = example.get("instruction", "").strip()
            output_text = example.get("output", "").strip()

            if not instruction or not output_text:
                continue

            # Truncate to max_seq_length characters (rough approximation)
            max_chars = config["max_seq_length"] * 3  # ~3 chars per token
            instruction = instruction[:max_chars // 3]
            output_text = output_text[:max_chars * 2 // 3]

            chat_example = {
                "messages": [
                    {"role": "user", "content": instruction},
                    {"role": "assistant", "content": output_text},
                ]
            }

            fout.write(json.dumps(chat_example) + "\n")
            valid_count += 1

    # Create a small validation split (last 10%)
    val_path = config["output_dir"] / "valid.jsonl"
    all_lines = output_path.read_text().strip().split("\n")
    split_idx = max(1, int(len(all_lines) * 0.9))

    with open(output_path, "w") as f:
        f.write("\n".join(all_lines[:split_idx]) + "\n")
    with open(val_path, "w") as f:
        f.write("\n".join(all_lines[split_idx:]) + "\n")

    logger.info(f"✓ Prepared {split_idx} training + {len(all_lines) - split_idx} validation examples")
    return output_path


def run_finetuning(config: dict):
    """Run MLX LoRA fine-tuning via mlx_lm.lora CLI."""
    logger.info(f"🚀 Starting fine-tuning: {config['name']}")
    logger.info(f"   Base model: {config['base_model']}")
    logger.info(f"   LoRA rank:  {config['lora_rank']}")
    logger.info(f"   Epochs:     {config['num_epochs']}")
    logger.info(f"   Batch size: {config['batch_size']}")

    adapter_dir = config["output_dir"] / "adapters"
    adapter_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "--model", config["base_model"],
        "--data", str(config["output_dir"]),
        "--adapter-path", str(adapter_dir),
        "--train",
        "--batch-size", str(config["batch_size"]),
        "--lora-layers", "16",
        "--lora-rank", str(config["lora_rank"]),
        "--iters", str(config["num_epochs"] * 500),  # Approximate
        "--learning-rate", str(config["learning_rate"]),
    ]

    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode != 0:
        logger.error(f"❌ Fine-tuning failed with exit code {result.returncode}")
        sys.exit(1)

    logger.info(f"✅ Fine-tuning complete! Adapter saved to: {adapter_dir}")
    return adapter_dir


def fuse_model(config: dict):
    """Fuse LoRA adapters into base model for Ollama export."""
    adapter_dir = config["output_dir"] / "adapters"
    fused_dir = config["output_dir"] / "fused"
    fused_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Fusing LoRA adapters into base model...")

    cmd = [
        sys.executable, "-m", "mlx_lm.fuse",
        "--model", config["base_model"],
        "--adapter-path", str(adapter_dir),
        "--save-path", str(fused_dir),
    ]

    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode != 0:
        logger.error("❌ Model fusion failed")
        sys.exit(1)

    logger.info(f"✅ Fused model saved to: {fused_dir}")
    return fused_dir


def export_to_gguf(config: dict):
    """Convert fused model to GGUF format for Ollama."""
    fused_dir = config["output_dir"] / "fused"
    gguf_path = config["output_dir"] / f"{config['name']}.gguf"

    logger.info("Converting to GGUF format for Ollama...")

    # mlx_lm can convert to GGUF
    cmd = [
        sys.executable, "-m", "mlx_lm.convert",
        "--hf-path", str(fused_dir),
        "--mlx-path", str(config["output_dir"] / "mlx-export"),
        "-q",  # Quantize for efficiency
    ]

    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode != 0:
        logger.warning("⚠ Direct GGUF conversion not available via mlx_lm.")
        logger.info("Alternative: Use llama.cpp to convert:")
        logger.info(f"  python3 convert_hf_to_gguf.py {fused_dir} --outfile {gguf_path} --outtype q4_0")
        return None

    logger.info(f"✅ GGUF model saved to: {gguf_path}")
    return gguf_path


def main():
    parser = argparse.ArgumentParser(description="Fine-tune ScholarFlow models on Apple Silicon")
    parser.add_argument(
        "--model",
        choices=["base", "studio", "qa"],
        required=True,
        help="Which model to fine-tune: base (general), studio (writing), qa (Q&A)",
    )
    parser.add_argument("--skip-data-prep", action="store_true", help="Skip training data preparation")
    parser.add_argument("--fuse-only", action="store_true", help="Only fuse existing adapters (skip training)")

    args = parser.parse_args()
    config = MODEL_CONFIGS[args.model]

    logger.info(f"═══ Fine-tuning: {config['name']} — {config['description']} ═══")

    # Check system
    mem_gb = check_system()

    # Reduce settings for low-memory systems
    if mem_gb < 16:
        config["batch_size"] = 1
        config["max_seq_length"] = 1024
        config["lora_rank"] = 8
        logger.info("→ Using reduced settings for low-memory system")

    # Prepare data
    if not args.skip_data_prep and not args.fuse_only:
        prepare_training_data(config)

    # Fine-tune
    if not args.fuse_only:
        run_finetuning(config)

    # Fuse adapters
    fuse_model(config)

    # Export
    export_to_gguf(config)

    logger.info("")
    logger.info("═══════════════════════════════════════")
    logger.info(f"✅ {config['name']} fine-tuning complete!")
    logger.info("═══════════════════════════════════════")
    logger.info("")
    logger.info("Next: Register with Ollama:")
    logger.info(f"  bash scripts/mac/register_finetuned.sh")


if __name__ == "__main__":
    main()
