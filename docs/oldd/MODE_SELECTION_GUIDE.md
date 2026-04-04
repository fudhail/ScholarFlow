# 📝 Quick Reference: Research Mode vs Studio Mode

## When to Use Each Mode

### 🔍 Research Mode (Default)

**Use when you're**:
- Learning about papers and topics
- Exploring literature in a field
- Discovering relevant research
- Understanding methodologies
- Building your knowledge base
- Reviewing existing work

**What happens**:
- Fast paper relevance scoring (100-150ms per paper)
- Quick literature assessments
- Optimized for speed and accuracy
- Uses `scholarflow-search` model (1B params)
- Focus: **Understanding existing research**

**Example queries**:
- "Find papers on transformer architectures"
- "What are the latest developments in computer vision?"
- "Explain the methodology used in this paper"
- "Show me related work on RAG systems"

---

### ✍️ Studio Mode (Writing/Drafting)

**Use when you're**:
- Writing your own paper
- Drafting sections (intro, methods, results, discussion)
- Creating literature reviews
- Composing original research
- Building your research paper
- Need plagiarism-free content

**What happens**:
- Original academic writing (500-1500ms per section)
- Human-like quality output
- Anti-plagiarism techniques applied
- Uses `scholarflow-studio` model (3B params)
- Focus: **Creating original academic content**

**Example queries**:
- "Write the introduction section for my paper on..."
- "Draft a literature review on transformer architectures"
- "Help me write the methodology section"
- "Create the results section from my experimental data"

---

## How to Switch Modes

### In Code (Backend)

```python
# When creating workflow state
state = create_initial_state(
    query="User's request",
    project_id="project_123",
    operation_mode="studio"  # or "research" (default)
)
```

### In Frontend (Future Enhancement)

```typescript
// Mode selector in UI
<ModeToggle 
  value={mode} 
  onChange={(m) => setMode(m)}
  options={[
    { value: "research", label: "🔍 Research Mode", desc: "Learn & explore" },
    { value: "studio", label: "✍️ Studio Mode", desc: "Write & create" }
  ]}
/>

// In API request
const response = await api.chat({
  query: userQuery,
  projectId: currentProject.id,
  operationMode: mode  // "research" or "studio"
});
```

---

## Model Selection Logic

```
User Query → Intent Detection → Mode Selection → Model Selection

Research Intent:
  ├─ "Find papers..." → Research Mode → scholarflow-search (1B)
  ├─ "What is..." → Research Mode → scholarflow-search (1B)
  └─ "Explain..." → Research Mode → scholarmate (3B)

Studio Intent:
  ├─ "Write introduction..." → Studio Mode → scholarflow-studio (3B)
  ├─ "Draft section..." → Studio Mode → scholarflow-studio (3B)
  └─ "Create paper..." → Studio Mode → scholarflow-studio (3B)
```

---

## Model Specifications

| Feature | Research Mode | Studio Mode |
|---------|---------------|-------------|
| **Model** | scholarflow-search | scholarflow-studio |
| **Size** | 1B params (1.3 GB) | 3B params (2.0 GB) |
| **Speed** | 100-150ms | 500-1500ms |
| **Temperature** | 0.2 (deterministic) | 0.75 (creative) |
| **Context** | 2048 tokens | 8192 tokens |
| **Purpose** | Fast scoring | Quality writing |
| **Output** | Relevance scores (0.0-1.0) | Academic paragraphs |
| **Focus** | Speed + accuracy | Originality + quality |

---

## Key Differences

### Research Mode Characteristics
✅ Fast inference (2-3x faster)  
✅ Consistent scoring  
✅ Optimized for ranking  
✅ Deterministic output  
✅ Focus on relevance assessment  

### Studio Mode Characteristics
✅ Human-like writing  
✅ Plagiarism-free content  
✅ Original synthesis  
✅ Section-aware prompts  
✅ Focus on quality and originality  

---

## Example Workflows

### Research Workflow
```
1. User: "Find papers on LLM evaluation"
2. System: [Research Mode] → scholarflow-search
3. Result: Ranked list of relevant papers (0.85, 0.82, 0.78...)
4. User: "Tell me about the top paper"
5. System: [Research Mode] → scholarmate
6. Result: Explanation of paper methodology and findings
```

### Studio Workflow
```
1. User: "Write introduction for my paper on LLM evaluation"
2. System: [Studio Mode] → scholarflow-studio
3. Result: Original academic paragraph with citations
4. User: "Now write the methodology section"
5. System: [Studio Mode] → scholarflow-studio
6. Result: Detailed methods with reproducible steps
```

---

## Best Practices

### For Research Mode
- Use for literature discovery and exploration
- Great for understanding paper relationships
- Fast enough for real-time ranking
- Ideal for building knowledge base

### For Studio Mode
- Use for all original writing tasks
- Provide clear section context (intro, methods, results, discussion)
- Include relevant citations in context
- Review output for coherence and accuracy
- Edit for your specific research context

---

## Performance Tips

1. **Keep Models in Memory**: `keep_alive=-1` (default in config)
2. **Use Batch Processing**: Score multiple papers in parallel
3. **Cache Results**: Store relevance scores to avoid re-scoring
4. **Section-by-Section**: Draft papers incrementally, not all at once
5. **Provide Context**: Give studio model access to relevant papers

---

## Troubleshooting

### Research mode is slow
- Check if `scholarflow-search` model is loaded
- Verify temperature is 0.2 (deterministic)
- Ensure keep_alive is enabled

### Studio writing quality is poor
- Verify `scholarflow-studio` model is being used
- Check temperature is 0.75 (creative)
- Provide more context (papers, data, section type)
- Review section-specific prompts

### Wrong model being used
- Check operation_mode in state: "research" or "studio"
- Verify mode parameter in generate_text() call
- Check logs for model name: "Generation (studio model, mode=studio)"

---

## Future Enhancements

- [ ] Auto-detect mode from query intent
- [ ] UI toggle for mode selection
- [ ] Section-specific model selection
- [ ] Fine-tuned models on academic papers
- [ ] Citation-aware writing model
- [ ] Multi-language support

---

**Key Takeaway**: Use **Research Mode** for learning and exploration, **Studio Mode** for original paper creation. The system automatically selects the optimized model for each workflow.
