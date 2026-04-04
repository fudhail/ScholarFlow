# Training Data Strategy - How Models Learn to Write Papers

## The Problem

**Old approach (abstracts only):**
```
Input: "Write an introduction about neural networks"
Training: Only learned from abstracts (100-200 words)
Output: Generic, chatbot-like text
```

**New approach (full sections):**
```
Input: "Write an introduction about neural networks"
Training: Learned from 200+ real introduction sections (500-2000 words each)
Output: Natural, academic-style introduction with proper structure
```

---

## What the Training Data Teaches

### 1. How to Write Each Section

**Introduction Sections** (200+ examples)
- Research motivation
- Problem statement
- Related work overview
- Paper contributions
- Structure preview

**Methodology Sections** (200+ examples)
- Approach description
- Algorithm details
- Experimental setup
- Implementation specifics

**Results Sections** (200+ examples)
- Findings presentation
- Data analysis
- Performance metrics
- Comparison with baselines

**Conclusion Sections** (200+ examples)
- Summary of contributions
- Implications
- Limitations
- Future work

---

### 2. How Papers Are Structured

Training examples include:
```
Q: "What sections should a paper on reinforcement learning include?"
A: "Abstract → Introduction → Related Work → Methodology → 
    Experiments → Results → Discussion → Conclusion → References"
```

This teaches the model:
- Standard paper structure
- Section order
- Purpose of each section
- How sections connect

---

### 3. How to Generate Research Plans

Training examples like:
```
Input: "Create a research plan for improving transformer efficiency"
Output: 
"Research Plan:
1. Problem Analysis: Current transformers require O(n²) attention...
2. Proposed Approach: Linear attention mechanism using kernel methods...
3. Methodology: Implement kernel approximation, test on benchmarks...
4. Expected Outcomes: 10x speed improvement with minimal accuracy loss..."
```

This teaches the model to:
- Break down research problems
- Propose methodologies
- Plan experiments
- Predict outcomes

---

### 4. Academic Writing Style

From reading 200+ real papers, the model learns:

**Natural patterns:**
- "We demonstrate that..." (active voice when appropriate)
- "Prior work has shown..." (proper citations)
- "Interestingly, our results..." (analytical thinking)
- Varied sentence structure
- Field-specific terminology

**What to avoid:**
- "In today's modern world..." (filler)
- "Firstly, secondly, thirdly..." (robotic lists)
- "It is important to note that..." (unnecessary hedging)

---

## Training Data Collection Process

### Step 1: Download Full Papers
```bash
python scripts/collect_training_data.py
```

**What happens:**
1. Fetches 1000 papers from ArXiv (CS.AI, CS.CL, CS.LG, CS.CV)
2. Downloads PDF files
3. Extracts full text from PDFs

### Step 2: Parse Sections

Script identifies sections by common headers:
- "1. Introduction" or "Introduction"
- "2. Methodology" or "Methods"
- "3. Experiments" or "Results"
- "4. Discussion"
- "5. Conclusion"

### Step 3: Create Training Examples

For each paper with sections, creates:
- **Introduction writing task**: "Write intro for [topic]" → actual intro text
- **Methodology writing task**: "Write methods for [research]" → actual methods
- **Results writing task**: "Present results for [experiment]" → actual results
- **Conclusion writing task**: "Conclude [paper]" → actual conclusion
- **Research plan task**: "Plan research for [topic]" → structured plan
- **Structure task**: "What sections for [paper]?" → section list
- **Summary task**: "Summarize [paper]" → comprehensive summary

**Total examples:** ~1,400 (200 papers × 7 tasks each)

---

## Comparison: Old vs New

### Old Training Data (abstracts only)

```json
{
  "instruction": "Summarize this paper: [abstract]",
  "output": "This paper presents [title]..."
}
```

**Problems:**
- Only 200-word abstracts
- No section structure
- No writing style examples
- Generic outputs

### New Training Data (full sections)

```json
{
  "instruction": "Write an introduction section for research on attention mechanisms...",
  "output": "Attention mechanisms have emerged as a critical component in modern neural architectures (Vaswani et al., 2017). Traditional sequence-to-sequence models relied exclusively on recurrent connections, which imposed significant computational constraints. The introduction of attention addresses these limitations by enabling direct connections between arbitrary sequence positions...[continues for 1500 words]"
}
```

**Benefits:**
- Real introduction text (500-2000 words)
- Natural academic style
- Proper citations and structure
- Realistic examples

---

## How This Improves RAG + Model

### Before (generic model):

```
User: "Write an introduction about transformers"
       ↓
   [RAG retrieves 5 transformer papers]
       ↓
   [Generic model generates]
       ↓
Output: "Transformers are neural networks. They use attention. 
         They work well for many tasks."
```

**Problem:** Generic, non-academic style

### After (fine-tuned on sections):

```
User: "Write an introduction about transformers"
       ↓
   [RAG retrieves 5 transformer papers]
       ↓
   [Fine-tuned model generates]
       ↓
Output: "The Transformer architecture fundamentally reimagined 
         sequence modeling by replacing recurrent connections 
         with self-attention mechanisms (Vaswani et al., 2017). 
         This architectural shift enables parallel computation 
         while maintaining the ability to capture long-range 
         dependencies, addressing key limitations of prior RNN 
         and LSTM-based approaches. Subsequent work has 
         demonstrated the broad applicability of this paradigm 
         across domains including natural language processing 
         (Devlin et al., 2018), computer vision (Dosovitskiy 
         et al., 2020), and multimodal learning..."
```

**Result:** Academic style, proper flow, natural writing

---

## Training Timeline

| Step | Time | Output |
|------|------|--------|
| 1. Download papers | 2-3 hours | 200 PDFs |
| 2. Extract sections | 30 min | Parsed text |
| 3. Create examples | 5 min | 1,400 examples |
| 4. Fine-tune model | 3-6 hours | Trained model |
| **Total** | **6-10 hours** | **Research writing AI** |

---

## Expected Quality

### Introduction Writing

**Prompt:**
```
Write an introduction for a paper on "Few-shot learning for text classification"
```

**Output (after training on 200+ intros):**
```
Few-shot learning has emerged as a critical challenge in machine learning, 
particularly as the scarcity of labeled data continues to limit model 
deployment across specialized domains (Snell et al., 2017). Traditional 
supervised learning paradigms require thousands of labeled examples per 
class, making them impractical for applications where data annotation is 
prohibitively expensive or technically infeasible.

Recent advances in meta-learning have demonstrated promising approaches 
to this challenge, with methods such as MAML (Finn et al., 2017) and 
Prototypical Networks (Snell et al., 2017) achieving notable success 
in computer vision tasks. However, the application of these techniques 
to natural language processing presents unique challenges due to the 
discrete and compositional nature of language...

This work makes the following contributions: (1) we introduce a novel 
few-shot learning framework tailored for text classification that 
leverages pretrained language models...
```

**Quality markers:**
- ✅ Proper academic tone
- ✅ Citation integration
- ✅ Problem motivation
- ✅ Contribution statement
- ✅ Natural flow

### Methodology Writing

**Prompt:**
```
Write a methodology section for sentiment analysis using BERT
```

**Output (after training on 200+ methods sections):**
```
3.1 Model Architecture

Our approach builds upon the BERT architecture (Devlin et al., 2018), 
which employs bidirectional transformers to learn contextualized word 
representations. We fine-tune the pretrained BERT-base model (110M 
parameters) using task-specific classification layers.

Formally, given an input sequence x = (x₁, x₂, ..., xₙ), BERT produces 
contextualized embeddings h = BERT(x). We append a classification head 
consisting of a linear projection followed by softmax:

p(y|x) = softmax(Wh[CLS] + b)

where h[CLS] represents the embedding of the special [CLS] token.

3.2 Training Procedure

We employ the following hyperparameters: learning rate 2e-5, batch 
size 32, and 3 training epochs. We use the AdamW optimizer with 
linear warmup over the first 10% of steps...
```

**Quality markers:**
- ✅ Technical precision
- ✅ Mathematical notation
- ✅ Implementation details
- ✅ Proper section structure

---

## Next Steps

1. **Run data collection:**
   ```bash
   pip install arxiv PyPDF2
   python scripts/collect_training_data.py
   ```

2. **Verify data quality:**
   - Check `data/training/scholarmate_training.jsonl`
   - Ensure diverse section examples
   - Validate text extraction quality

3. **Fine-tune models:**
   ```bash
   python scripts/finetune_qa_model.py      # For summaries/Q&A
   python scripts/finetune_studio_model.py  # For paper writing
   ```

4. **Test outputs:**
   - Compare before/after quality
   - Test different section types
   - Validate academic style

---

## Troubleshooting

**PDF extraction fails?**
- Some PDFs are image-based (not text)
- Use OCR if needed: `pip install pytesseract`
- Alternative: Use LaTeX source from ArXiv

**Sections not detected?**
- Papers use non-standard headers
- Adjust regex patterns in `parse_paper_sections()`
- Manually verify section extraction

**Poor quality output?**
- Need more training examples (increase from 200 to 500)
- Longer training (3 epochs → 5 epochs)
- Check section extraction quality

---

## Summary

**Key insight:** To teach models to write like researchers, train them on actual research paper sections, not just abstracts.

**What the model learns:**
- ✅ Section-specific writing styles
- ✅ Paper structure and flow
- ✅ Academic vocabulary and tone
- ✅ Research planning
- ✅ Natural synthesis (not copying)

**Result:** RAG provides facts, fine-tuned model writes them like a real researcher.
