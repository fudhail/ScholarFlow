#!/bin/bash
# ================================================================
# ScholarFlow — Ollama Performance Benchmark (macOS)
# Tests model speeds and Apple Silicon Metal acceleration
# ================================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     ScholarFlow — Model Benchmark (macOS)                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# System Info
echo -e "${BLUE}System Info:${NC}"
echo "  Chip: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'Unknown')"
ARCH=$(uname -m)
MEM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')
echo "  Arch: $ARCH"
echo "  Memory: ${MEM_GB}GB"
echo ""

# List installed models
echo -e "${BLUE}Installed Models:${NC}"
ollama list 2>/dev/null || echo "  (Ollama not running)"
echo ""

# Benchmark function
benchmark_model() {
    local MODEL_NAME="$1"
    local PROMPT="$2"
    local LABEL="$3"

    echo -e "${BLUE}Testing: $LABEL ($MODEL_NAME)${NC}"

    START=$(python3 -c "import time; print(time.time())")
    RESPONSE=$(ollama run "$MODEL_NAME" "$PROMPT" 2>/dev/null | head -5)
    END=$(python3 -c "import time; print(time.time())")

    ELAPSED=$(python3 -c "print(f'{$END - $START:.2f}')")
    CHARS=${#RESPONSE}

    echo -e "  ${GREEN}✓${NC} Response: ${ELAPSED}s (${CHARS} chars)"
    echo ""
}

echo "═══════════════════════════════════════"
echo "  Running benchmarks..."
echo "═══════════════════════════════════════"
echo ""

# Benchmark each model
PROMPT="Explain the significance of attention mechanisms in transformer models in exactly 3 sentences."

benchmark_model "scholarmate-fast" "$PROMPT" "Fast Model (1B - Routing/Ranking)"
benchmark_model "scholarflow-search" "Rate relevance of a paper titled 'BERT: Pre-training of Deep Bidirectional Transformers' to the query 'attention mechanisms in NLP'. Return only a score 0.0-1.0." "Search Model (1B - Relevance Scoring)"
benchmark_model "scholarmate" "$PROMPT" "Smart Model (3B - Research Co-Author)"
benchmark_model "scholarflow-studio" "Write a 3-sentence introduction for a paper on transformer attention mechanisms in NLP." "Studio Model (3B - Academic Writing)"

echo "═══════════════════════════════════════"
echo -e "${GREEN}  Benchmark complete!${NC}"
echo "═══════════════════════════════════════"
echo ""
echo "Tips for better performance on Mac:"
echo "  • Close memory-heavy apps (Chrome, Docker)"
echo "  • Ensure Ollama has OLLAMA_KEEP_ALIVE=300 (5min keep-alive)"
echo "  • Apple Silicon uses Metal GPU automatically"
echo "  • 1B models: ~0.3-0.8s | 3B models: ~1-3s (M1/M2/M3)"
echo ""
