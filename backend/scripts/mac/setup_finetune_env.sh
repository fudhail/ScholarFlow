#!/bin/bash
# ================================================================
# ScholarFlow — Fine-Tuning on Mac (Apple Silicon)
# Uses MLX for Apple Silicon native training (no CUDA needed)
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ScholarFlow — Fine-Tuning Environment Setup (macOS)       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 1: Check Apple Silicon
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/5]${NC} Checking system..."

ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo -e "${RED}❌ Apple Silicon (M1/M2/M3/M4) is required for MLX fine-tuning.${NC}"
    echo "   Intel Macs should use Google Colab or a cloud GPU instead."
    echo "   See: docs/CUSTOM_MODELS_SETUP.md for Colab instructions."
    exit 1
fi
echo -e "${GREEN}  ✓ Apple Silicon detected${NC}"

MEM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')
echo "  → Unified memory: ${MEM_GB}GB"

if [ "$MEM_GB" -lt 16 ]; then
    echo -e "${YELLOW}  ⚠ Warning: 16GB+ recommended for 3B fine-tuning${NC}"
    echo "    → Will use 1B model and reduced settings instead"
fi

# ─────────────────────────────────────────────────────────────────
# Step 2: Install Python dependencies
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[2/5]${NC} Installing fine-tuning dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Install with: brew install python@3.11${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}  ✓ Python $PYTHON_VERSION${NC}"

# Install MLX dependencies
pip3 install --quiet --upgrade \
    mlx>=0.5.0 \
    mlx-lm>=0.4.0 \
    huggingface-hub \
    transformers \
    datasets \
    PyPDF2 \
    arxiv

echo -e "${GREEN}  ✓ MLX fine-tuning dependencies installed${NC}"

# ─────────────────────────────────────────────────────────────────
# Step 3: Create data directories
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[3/5]${NC} Setting up directories..."

mkdir -p "$BACKEND_DIR/data/training"
mkdir -p "$BACKEND_DIR/data/papers/pdfs"
mkdir -p "$BACKEND_DIR/models/adapters"
mkdir -p "$BACKEND_DIR/models/mlx-finetuned"

echo -e "${GREEN}  ✓ Directories created${NC}"

# ─────────────────────────────────────────────────────────────────
# Step 4: Download training data
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/5]${NC} Checking training data..."

TRAINING_FILE="$BACKEND_DIR/data/training/scholarmate_training.jsonl"

if [ -f "$TRAINING_FILE" ]; then
    LINE_COUNT=$(wc -l < "$TRAINING_FILE" | tr -d ' ')
    echo -e "${GREEN}  ✓ Training data exists ($LINE_COUNT examples)${NC}"
else
    echo -e "${YELLOW}  ⚠ No training data found. Run the collection script first:${NC}"
    echo "    cd $BACKEND_DIR && python3 scripts/collect_training_data.py"
    echo ""
    echo "  This will download ~200 ArXiv papers and create training examples."
    echo "  Estimated time: 15-30 minutes (depends on internet speed)"
fi

# ─────────────────────────────────────────────────────────────────
# Step 5: Summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅  Fine-tuning environment ready!                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps (in order):"
echo ""
echo "  1. Collect training data (if not done):"
echo "     cd $BACKEND_DIR"
echo "     python3 scripts/collect_training_data.py"
echo ""
echo "  2. Fine-tune models with MLX on Apple Silicon:"
echo "     python3 scripts/mac/finetune_mlx.py --model studio"
echo "     python3 scripts/mac/finetune_mlx.py --model qa"
echo ""
echo "  3. Register fine-tuned models with Ollama:"
echo "     bash scripts/mac/register_finetuned.sh"
echo ""
echo "See docs/CUSTOM_MODELS_SETUP.md for full guide."
echo ""
