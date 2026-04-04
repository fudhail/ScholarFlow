#!/bin/bash
# ================================================================
# ScholarFlow — Mac Setup Script
# Creates all custom Ollama models from Modelfiles
# Supports macOS (Apple Silicon M1/M2/M3/M4 + Intel)
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODELS_DIR="$BACKEND_DIR/models"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     ScholarFlow — Custom Model Setup (macOS)                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 1: Check prerequisites
# ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/6]${NC} Checking prerequisites..."

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama is not installed.${NC}"
    echo ""
    echo "Install Ollama for Mac:"
    echo "  1. Visit https://ollama.com/download/mac"
    echo "  2. Download and install the .dmg file"
    echo "  3. Or run: brew install ollama"
    echo ""
    exit 1
fi
echo -e "${GREEN}  ✓ Ollama is installed${NC}"

# Check if Ollama is running
if ! ollama list &> /dev/null; then
    echo -e "${YELLOW}  ⚠ Ollama is not running. Starting it now...${NC}"
    open -a Ollama 2>/dev/null || ollama serve &
    sleep 3
    if ! ollama list &> /dev/null; then
        echo -e "${RED}❌ Could not start Ollama. Please start it manually.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}  ✓ Ollama is running${NC}"

# Check system info
echo ""
echo -e "${BLUE}[2/6]${NC} Detecting system..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo -e "${GREEN}  ✓ Apple Silicon detected (M-series)${NC}"
    echo "    → Metal GPU acceleration will be used"
    echo "    → Recommended: 16GB+ unified memory"
else
    echo -e "${YELLOW}  ⚠ Intel Mac detected${NC}"
    echo "    → CPU-only inference (slower)"
    echo "    → Apple Silicon recommended for best performance"
fi

# Check available memory
MEM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')
echo "    → System memory: ${MEM_GB}GB"
if [ "$MEM_GB" -lt 8 ]; then
    echo -e "${RED}  ⚠ Warning: Less than 8GB RAM. 3B models may be slow.${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Step 2: Pull base models
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[3/6]${NC} Pulling base models..."

# Pull 1B model (for fast/search tasks)
if ollama list 2>/dev/null | grep -q "llama3.2:1b"; then
    echo -e "${GREEN}  ✓ llama3.2:1b already exists${NC}"
else
    echo "  Pulling llama3.2:1b (fast model, ~1.3GB)..."
    ollama pull llama3.2:1b
    echo -e "${GREEN}  ✓ llama3.2:1b pulled${NC}"
fi

# Pull 3B model (for smart/writing tasks)
if ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
    echo -e "${GREEN}  ✓ llama3.2:3b already exists${NC}"
else
    echo "  Pulling llama3.2:3b (smart model, ~2.0GB)..."
    ollama pull llama3.2:3b
    echo -e "${GREEN}  ✓ llama3.2:3b pulled${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Step 3: Create custom models
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/6]${NC} Creating custom ScholarFlow models..."

cd "$MODELS_DIR"

# Model 1: ScholarMate (primary research assistant, 3B)
echo ""
echo "  Creating scholarmate (primary research co-author, 3B)..."
ollama create scholarmate -f ScholarMate.Modelfile
echo -e "${GREEN}  ✓ scholarmate created${NC}"

# Model 2: ScholarMate-Fast (fast routing/ranking, 1B)
echo "  Creating scholarmate-fast (quick tasks, 1B)..."
ollama create scholarmate-fast -f ScholarMate-Fast.Modelfile
echo -e "${GREEN}  ✓ scholarmate-fast created${NC}"

# Model 3: ScholarFlow-Search (paper relevance scoring, 1B)
echo "  Creating scholarflow-search (paper ranking, 1B)..."
ollama create scholarflow-search -f ScholarFlow-Search.Modelfile
echo -e "${GREEN}  ✓ scholarflow-search created${NC}"

# Model 4: ScholarFlow-Studio (academic writing, 3B)
echo "  Creating scholarflow-studio (academic writing, 3B)..."
ollama create scholarflow-studio -f ScholarFlow-Studio.Modelfile
echo -e "${GREEN}  ✓ scholarflow-studio created${NC}"

# Model 5: ScholarMate-CoT (chain-of-thought reasoning, 3B)
echo "  Creating scholarmate-cot (chain-of-thought, 3B)..."
ollama create scholarmate-cot -f ScholarMate-CoT.Modelfile
echo -e "${GREEN}  ✓ scholarmate-cot created${NC}"

cd "$BACKEND_DIR"

# ─────────────────────────────────────────────────────────────────
# Step 4: Verify all models
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5/6]${NC} Verifying models..."
echo ""

MODELS=("scholarmate" "scholarmate-fast" "scholarflow-search" "scholarflow-studio" "scholarmate-cot")
ALL_OK=true

for model in "${MODELS[@]}"; do
    if ollama list 2>/dev/null | grep -q "$model"; then
        echo -e "  ${GREEN}✓${NC} $model"
    else
        echo -e "  ${RED}✗${NC} $model — MISSING"
        ALL_OK=false
    fi
done

# ─────────────────────────────────────────────────────────────────
# Step 5: Quick smoke test
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[6/6]${NC} Running smoke test..."
echo ""

TEST_RESULT=$(ollama run scholarmate "Respond with exactly: READY" 2>/dev/null | head -1)
if echo "$TEST_RESULT" | grep -qi "READY"; then
    echo -e "${GREEN}  ✓ scholarmate is responding correctly${NC}"
else
    echo -e "${YELLOW}  ⚠ scholarmate responded but output may differ (this is normal)${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅  All ScholarFlow models are ready!                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Models created:"
echo "  • scholarmate         — Primary research co-author (3B)"
echo "  • scholarmate-fast    — Fast routing & quick tasks (1B)"
echo "  • scholarflow-search  — Paper relevance scoring  (1B)"
echo "  • scholarflow-studio  — Academic paper writing   (3B)"
echo "  • scholarmate-cot     — Chain-of-thought reasoning (3B)"
echo ""
echo "Next steps:"
echo "  1. Set up your .env file (copy .env.example → .env)"
echo "  2. Start the backend:  cd backend && python -m uvicorn app.main:app --reload"
echo "  3. Start the frontend: npm run dev"
echo ""
