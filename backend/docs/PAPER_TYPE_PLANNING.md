# Paper Type-Aware Planning Training

## Why Different Paper Types Need Different Structures

Not all research papers are the same! The model needs to understand that:

**Experimental Paper** ≠ **Theoretical Paper** ≠ **Survey Paper** ≠ **Application Paper**

Each type has:
- Different section structures
- Different writing styles
- Different evaluation criteria
- Different reader expectations

---

## Four Main Paper Types

### 1. Experimental Papers (Most Common in ML/AI)

**Purpose:** Present new methods with empirical validation

**Structure:**
```
1. Abstract
2. Introduction
   - Problem motivation
   - Research gap
   - Contributions
3. Related Work
   - Prior methods
   - Comparison with existing work
4. Methodology
   - Proposed approach
   - Algorithm details
   - Design choices
5. Experiments
   - Datasets
   - Baselines
   - Experimental setup
   - Hyperparameters
6. Results
   - Performance metrics
   - Quantitative analysis
   - Ablation studies
7. Discussion
   - Result interpretation
   - Limitations
8. Conclusion
   - Summary of contributions
   - Future work
9. References
```

**Example Topics:**
- "A Novel Attention Mechanism for Image Classification"
- "Improving BERT with Dynamic Masking"
- "Few-Shot Learning via Meta-Learning"

---

### 2. Theoretical Papers

**Purpose:** Develop mathematical foundations and formal proofs

**Structure:**
```
1. Abstract
2. Introduction
   - Theoretical motivation
   - Main results preview
3. Preliminaries
   - Notation
   - Definitions
   - Background theory
4. Main Results
   - Theorems
   - Propositions
   - Corollaries
5. Proofs
   - Formal proofs
   - Lemmas
   - Mathematical derivations
6. Discussion
   - Implications
   - Connections to prior work
7. Conclusion
8. References
```

**Example Topics:**
- "Convergence Analysis of Stochastic Gradient Descent"
- "Theoretical Bounds for Neural Network Expressiveness"
- "Formal Verification of Attention Mechanisms"

---

### 3. Survey Papers

**Purpose:** Comprehensively review and synthesize existing research

**Structure:**
```
1. Abstract
2. Introduction
   - Survey scope
   - Taxonomy
   - Organization
3. Background
   - Historical context
   - Key concepts
4. Survey of Approaches
   - Method Category 1
   - Method Category 2
   - Method Category 3
5. Comparative Analysis
   - Strengths/weaknesses table
   - Performance comparison
   - Use case analysis
6. Discussion
   - Open challenges
   - Future directions
7. Conclusion
8. References (extensive)
```

**Example Topics:**
- "A Survey of Transformer Architectures"
- "Deep Learning for Computer Vision: A Review"
- "Meta-Learning: A Comprehensive Overview"

---

### 4. Application Papers

**Purpose:** Present practical systems and implementations

**Structure:**
```
1. Abstract
2. Introduction
   - Problem context
   - System overview
3. Related Work
   - Existing tools
   - Prior systems
4. System Design
   - Architecture
   - Components
   - Design decisions
5. Implementation
   - Technical details
   - Technologies used
   - Challenges
6. Evaluation
   - Use cases
   - Performance tests
   - User studies
7. Discussion
   - Lessons learned
   - Deployment experiences
8. Conclusion
9. References
```

**Example Topics:**
- "ScholarFlow: An AI Research Assistant"
- "A Real-Time Translation System for Medical Documents"
- "FastBERT: An Optimized Inference Engine"

---

## How Training Teaches Paper Type Planning

### Training Example 1: Type Identification

**Input:**
```
Analyze this paper and determine what type it is:

Title: "Attention Is All You Need"
Abstract: "We propose a new architecture based solely on attention 
mechanisms... We show that the Transformer achieves 28.4 BLEU on 
WMT 2014 English-to-German translation..."
```

**Output:**
```
Paper Type: Experimental

This is an experimental paper. Based on the research objectives and 
methodology, the paper should include:

1. Abstract
2. Introduction
3. Related Work
4. Methodology
5. Experiments
6. Results
7. Discussion
8. Conclusion
9. References

Rationale: Experimental papers require this structure because they 
present experimental results and need sections for methodology, 
experiments, and analysis.
```

### Training Example 2: Planning Based on Type

**Input:**
```
Create a detailed research plan for writing an experimental paper on:

Title: "Few-Shot Learning with Meta-LSTM"
Objective: Develop a meta-learning approach using LSTMs for few-shot 
classification tasks...
```

**Output:**
```
Research Paper Plan (Experimental Paper)

Paper Type: Experimental

Proposed Structure:
   - Introduction
   - Related Work
   - Methodology
   - Experiments
   - Results
   - Discussion
   - Conclusion

Section Details:

1. Introduction:
Few-shot learning addresses the challenge of learning from limited 
labeled examples, which is critical for real-world applications where 
data collection is expensive. We propose Meta-LSTM...

2. Methodology:
Our approach leverages LSTMs as meta-learners to capture task-specific 
patterns. The architecture consists of an embedding network and a 
meta-learning module...

3. Results:
We evaluate on Omniglot and miniImageNet benchmarks. Our method achieves 
95.2% accuracy on 5-way 1-shot Omniglot, outperforming MAML by 2.1%...

Expected Contributions:
This experimental paper will advance the field by providing empirical 
evidence and experimental validation.
```

### Training Example 3: Planning Question

**Input:**
```
I want to write a research paper about proving convergence guarantees 
for a new optimization algorithm. What type of paper should this be 
and what sections do I need?
```

**Output:**
```
Based on your topic, this should be a theoretical paper.

Recommended Paper Structure:

1. **Abstract**
2. **Introduction** - Introduce the problem, motivation, and contributions
3. **Preliminaries** - Define notation and formal preliminaries
4. **Main Results** - State theorems and main results
5. **Proofs** - Provide mathematical proofs
6. **Discussion** - Interpret results and compare with baselines
7. **Conclusion** - Summarize contributions and future directions
8. **References**

Why this structure: Theoretical papers require formal analysis, so you 
need sections for preliminaries, theorems, and proofs.
```

---

## How the Model Uses This Knowledge

### Scenario 1: User Asks for Paper Plan

**User Input:**
```
"I want to write a paper about a new transformer variant with better 
efficiency. Help me plan it."
```

**Model Analysis:**
1. Identifies topic: new method + efficiency claims = **Experimental paper**
2. Determines required sections: Intro, Related Work, Methodology, Experiments, Results
3. Generates appropriate plan with:
   - Methodology section (describe the variant)
   - Experiments section (efficiency benchmarks)
   - Results section (speed/memory comparisons)

**Model Output:**
```
This should be an experimental paper. Here's your plan:

1. Introduction
   - Motivation: Transformer efficiency problems
   - Gap: Existing methods have O(n²) complexity
   - Contribution: Novel linear-time variant

2. Related Work
   - Survey efficient transformers (Linformer, Performer, etc.)
   - Position your approach

3. Methodology
   - Describe your efficient attention mechanism
   - Algorithm pseudocode
   - Complexity analysis

4. Experiments
   - Datasets: GLUE, WMT, etc.
   - Baselines: Standard Transformer, Linformer
   - Metrics: Speed (tokens/sec), memory usage, accuracy

5. Results
   - Efficiency gains (table/graphs)
   - Quality comparison (BLEU scores)
   - Ablation studies

6. Conclusion
   - Summary: 5x faster with minimal quality loss
   - Future: Apply to vision tasks
```

### Scenario 2: User Asks About Survey Paper

**User Input:**
```
"I need to write a survey of attention mechanisms. What structure 
should I use?"
```

**Model Analysis:**
1. Identifies "survey" keyword = **Survey paper**
2. Knows survey papers need: Background, Survey sections, Comparative Analysis
3. No experiments needed!

**Model Output:**
```
This is a survey paper. Structure:

1. Introduction
   - Scope: Attention mechanisms in NLP and vision
   - Taxonomy: Self-attention, cross-attention, multi-head

2. Background
   - Historical: RNNs → Attention → Transformers
   - Key concepts: Query, key, value

3. Survey of Approaches
   3.1 Dot-Product Attention (Bahdanau et al.)
   3.2 Multi-Head Attention (Vaswani et al.)
   3.3 Linear Attention (Katharopoulos et al.)
   3.4 Sparse Attention (Child et al.)

4. Comparative Analysis
   - Table: Method vs Complexity vs Performance
   - Use cases: When to use which variant

5. Open Challenges
   - Long sequences, interpretability

6. Conclusion
```

---

## Training Data Statistics

After running `collect_training_data.py`, you'll see:

```
📊 Paper Type Distribution:
  Experimental: 160 papers (80%)
  Application: 25 papers (12.5%)
  Theoretical: 10 papers (5%)
  Survey: 5 papers (2.5%)

📄 Section Statistics:
  introduction: 195 papers
  methodology: 180 papers
  experiments: 160 papers
  conclusion: 198 papers
  related_work: 150 papers

✅ Model will learn:
  - How to write 8 different section types
  - Structure for 4 paper types
  - Planning based on paper type and research goals
  - Section analysis and recommendations
```

---

## 10 Training Tasks Per Paper

For each paper with extracted sections, the model learns:

1. ✍️ **Write Introduction** - Real intro from that paper type
2. ✍️ **Write Methodology** - Type-appropriate methods section
3. ✍️ **Write Results** - Results format for that type
4. ✍️ **Write Conclusion** - Conclusion style for that type
5. 🎯 **Identify Paper Type** - "This is an X paper because..."
6. 📋 **Generate Plan** - Type-specific structured plan
7. 📝 **Summarize** - Paper summary mentioning type
8. 🔍 **Analyze Structure** - Why this structure is appropriate
9. 📖 **Write Related Work** - Literature review (if present)
10. ❓ **Answer Planning Question** - "What type/sections do I need?"

**Total: 200 papers × 10 tasks = 2,000 training examples**

---

## Benefits of Type-Aware Planning

### ✅ Before Type-Aware Training:

```
User: "Plan a paper on neural network convergence proofs"
Model: "You need: Intro, Methods, Experiments, Results, Conclusion"
```
❌ **Wrong!** No experiments in theoretical papers!

### ✅ After Type-Aware Training:

```
User: "Plan a paper on neural network convergence proofs"
Model: "This is a theoretical paper. You need:
1. Introduction - Motivation
2. Preliminaries - Definitions, notation
3. Main Results - Theorems
4. Proofs - Formal proofs
5. Discussion - Implications
6. Conclusion"
```
✅ **Correct!** Theoretical structure with proofs, no experiments!

---

## Real-World Examples

### Example 1: Experimental Paper Plan

**User:** "I have a new data augmentation technique for image classification. Plan my paper."

**Model Output:**
```
Paper Type: Experimental (new method + empirical validation)

Structure:
1. Introduction
   - Problem: Limited labeled data for image classification
   - Gap: Existing augmentation methods insufficient
   - Contribution: Novel semantic-preserving augmentation

2. Related Work
   - Traditional: Flip, rotate, crop
   - Deep learning: Cutout, Mixup, AutoAugment
   - Position your method

3. Methodology
   - Your augmentation algorithm
   - How it preserves semantics
   - Integration with training pipeline

4. Experiments
   - Datasets: CIFAR-10, ImageNet
   - Baselines: Cutout, Mixup, RandAugment
   - Metrics: Top-1/Top-5 accuracy
   - Ablation: Which augmentations matter?

5. Results
   - Accuracy improvements (tables)
   - Visualization of augmented images
   - Statistical significance tests

6. Discussion
   - Why your method works
   - When it helps most
   - Computational cost analysis

7. Conclusion
   - Summary: +2.3% on ImageNet
   - Future: Apply to detection
```

### Example 2: Survey Paper Plan

**User:** "I want to review all the NLP tasks transformers have been applied to."

**Model Output:**
```
Paper Type: Survey (comprehensive literature review)

Structure:
1. Introduction
   - Transformers revolutionized NLP
   - Survey scope: Tasks, not architectures
   - Organization by task type

2. Background
   - Transformer basics
   - Transfer learning paradigm

3. Survey of Applications
   3.1 Machine Translation (original application)
   3.2 Language Modeling (GPT series)
   3.3 Text Classification (BERT fine-tuning)
   3.4 Question Answering (SQuAD, etc.)
   3.5 Named Entity Recognition
   3.6 Summarization
   3.7 Generation (GPT-3, etc.)

4. Comparative Analysis
   - Table: Task → Best model → Performance
   - Which tasks benefit most?
   - Fine-tuning vs prompting

5. Open Challenges
   - Long documents
   - Low-resource languages
   - Interpretability

6. Conclusion & Future Directions
```

---

## Summary

The model now learns:

✅ **4 paper types** with different structures
✅ **10 training tasks** per paper
✅ **Type identification** from title/abstract
✅ **Appropriate section planning** for each type
✅ **Why structures differ** (rationale)

**Result:** When planning research, the model recommends the right structure based on paper type, not a one-size-fits-all template!
