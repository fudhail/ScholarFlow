# Backend Configuration for Chain-of-Thought Models

## Option A: Environment Variables (.env file)

Add these lines to `backend/.env`:

```bash
# Which Ollama model to use for smart tasks (synthesis, writing, analysis)
OLLAMA_MODEL_SMART=scholarmate-cot

# Enable explicit Chain-of-Thought reasoning
ENABLE_COT_REASONING=true

# Show thinking process to users in the UI
# false = keep thinking internal (save tokens)
# true = stream thinking to UI so users see model reasoning
SHOW_THINKING_TO_USER=false
```

---

## Option B: Direct Configuration (config.py)

Edit `backend/app/core/config.py` and find the Ollama configuration section:

```python
# ===== Ollama Config (Primary for hybrid mode) =====
ollama_base_url: str = "http://localhost:11434"
ollama_model_fast: str = "llama3.2:1b"                    # Keep as-is
ollama_model_smart: str = "scholarmate-cot"              # ← CHANGE: was "scholarmate"
ollama_model_search: str = "scholarflow-search"          # Keep as-is
ollama_model_studio: str = "scholarflow-studio"          # Keep as-is

# ===== Chain-of-Thought Settings =====
enable_cot_reasoning: bool = True                         # NEW: Enable CoT
show_thinking_to_user: bool = False                       # NEW: Show/hide thinking
```

---

## Configuration Options Explained

### OLLAMA_MODEL_SMART

```python
# Option 1: Standard Model (No explicit thinking)
ollama_model_smart: str = "scholarmate"

# Option 2: CoT Model (With explicit thinking)
ollama_model_smart: str = "scholarmate-cot"  # ← RECOMMENDED
```

**Difference:**
- `scholarmate`: Faster, no thinking shown
- `scholarmate-cot`: Enhanced system prompt for better reasoning, can show thinking

### ENABLE_COT_REASONING

```python
enable_cot_reasoning: bool = False   # Don't parse thinking tags
enable_cot_reasoning: bool = True    # ← RECOMMENDED: Parse and handle thinking
```

**What it does:**
- When True: Backend looks for `<thinking>...</thinking>` tags in responses
- Parses them and makes thinking available to UI
- No performance cost if model doesn't produce thinking

### SHOW_THINKING_TO_USER

```python
show_thinking_to_user: bool = False  # ← RECOMMENDED: Keep thinking internal
show_thinking_to_user: bool = True   # Show reasoning in UI (debug/educational)
```

**What it does:**
- When False: Thinking is available but not streamed to UI
  - Saves bandwidth
  - Cleaner UI
  - Model reasoning still used internally
  
- When True: User sees model's step-by-step thinking
  - Great for debugging
  - Educational (see how model reasons)
  - Uses more tokens (30% more bandwidth)

---

## 🎯 Recommended Configuration

For best results with current system:

```python
# backend/app/core/config.py

ollama_model_smart: str = "scholarmate-cot"
enable_cot_reasoning: bool = True
show_thinking_to_user: bool = False
```

**Why?**
- Uses enhanced model with better reasoning
- Extracts thinking for internal analysis
- Doesn't waste bandwidth streaming thinking to UI
- User still gets better quality responses

---

## Advanced Configurations

### Config A: Discovery (Fast, No Thinking)
```python
ollama_model_smart: str = "scholarmate"
enable_cot_reasoning: bool = False
show_thinking_to_user: bool = False
```
Use when: Speed matters, responses are simple

### Config B: Quality (Better Reasoning, Hidden)
```python
ollama_model_smart: str = "scholarmate-cot"
enable_cot_reasoning: bool = True
show_thinking_to_user: bool = False
```
Use when: Quality matters, want hidden reasoning

### Config C: Debug/Learning (See Everything)
```python
ollama_model_smart: str = "scholarmate-cot"
enable_cot_reasoning: bool = True
show_thinking_to_user: bool = True
```
Use when: Debugging, learning, demo/education

---

## How to Apply Changes

### 1. Edit the configuration

Edit `backend/.env` OR `backend/app/core/config.py`

### 2. Restart backend

```powershell
# Stop current backend (Ctrl+C if running in terminal)

# Restart:
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Test it

Make a research query in the UI. Response should work the same, just with better reasoning.

---

## Verification

### Step 1: Check model is configured
```python
# backend/app/core/config.py
print(settings.ollama_model_smart)  # Should print: scholarmate-cot
print(settings.enable_cot_reasoning)  # Should print: True
```

### Step 2: Run test
```powershell
cd backend
python tests/test_chain_of_thought.py
```

### Step 3: Test in UI
1. Make a research query
2. Watch logs: Should see thinking parsed (if enabled)
3. Avatar should speak narration
4. Formal response should display

---

## Environment Variable Precedence

1. **Highest priority**: Environment variables (.env file)
2. **Default**: Values in config.py

So if you set `OLLAMA_MODEL_SMART=scholarmate-cot` in .env, it overrides config.py

---

## Common Issues

### "Model not found: scholarmate-cot"
- Verify model created: `ollama list`
- Create it: `ollama create scholarmate-cot -f models/ScholarMate-CoT.Modelfile`

### "Changes not taking effect"
- Backend not restarted
- Using old .env file
- Setting wrong variable name (case-sensitive)

### "Slow responses"
- Normal with CoT (10-20% slower)
- Try `SHOW_THINKING_TO_USER=false` to reduce bandwidth

### "No thinking shown even with SHOW_THINKING_TO_USER=true"
- Using wrong model (still "scholarmate")
- Model not producing thinking tags
- Check browser console for errors

---

See also:
- [ENABLE_COT_QUICK_START.md](ENABLE_COT_QUICK_START.md) - Step-by-step setup
- [backend/docs/CHAIN_OF_THOUGHT_GUIDE.md](backend/docs/CHAIN_OF_THOUGHT_GUIDE.md) - Detailed guide
