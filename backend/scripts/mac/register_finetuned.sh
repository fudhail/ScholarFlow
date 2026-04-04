#!/bin/bash
# ================================================================
# Register fine-tuned models with Ollama on Mac
# Run AFTER finetune_mlx.py completes
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODELS_DIR="$BACKEND_DIR/models"
FINETUNED_DIR="$MODELS_DIR/mlx-finetuned"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Register Fine-Tuned Models with Ollama (macOS)            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama not found. Install from: https://ollama.com/download/mac${NC}"
    exit 1
fi

# Check if fine-tuned models exist and register them
register_model() {
    local MODEL_NAME="$1"
    local MODELFILE="$2"

    if [ -f "$MODELS_DIR/$MODELFILE" ]; then
        echo -e "${BLUE}  Creating $MODEL_NAME from $MODELFILE...${NC}"
        cd "$MODELS_DIR"
        ollama create "$MODEL_NAME" -f "$MODELFILE"
        echo -e "${GREEN}  ✓ $MODEL_NAME registered${NC}"
        cd "$BACKEND_DIR"
    else
        echo -e "${YELLOW}  ⚠ $MODELFILE not found — skipping $MODEL_NAME${NC}"
    fi
}

# Register fine-tuned models if adapters exist
if [ -d "$FINETUNED_DIR/scholarflow-studio/adapters" ]; then
    echo "Fine-tuned Studio model found. Registering..."
    register_model "scholarflow-studio" "ScholarFlow-Studio-FineTuned.Modelfile"
else
    echo "No fine-tuned Studio adapter. Using base prompt-tuned version..."
    register_model "scholarflow-studio" "ScholarFlow-Studio.Modelfile"
fi

if [ -d "$FINETUNED_DIR/scholarflow-qa/adapters" ]; then
    echo "Fine-tuned QA model found. Registering..."
    register_model "scholarflow-qa" "ScholarFlow-QA-FineTuned.Modelfile"
else
    echo "No fine-tuned QA adapter. Skipping QA model."
fi

# Always ensure base models are registered
register_model "scholarmate" "ScholarMate.Modelfile"
register_model "scholarmate-fast" "ScholarMate-Fast.Modelfile"
register_model "scholarflow-search" "ScholarFlow-Search.Modelfile"
register_model "scholarmate-cot" "ScholarMate-CoT.Modelfile"

echo ""
echo -e "${GREEN}✅ All available models registered with Ollama!${NC}"
echo ""
echo "Verify with: ollama list"
echo ""
