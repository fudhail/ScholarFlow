"""
Quick Test Script for Chain-of-Thought Models
Run this to verify your CoT setup is working correctly
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.ai_client import ai_client
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_standard_model():
    """Test current model without CoT"""
    print("\n" + "="*80)
    print("TEST 1: STANDARD MODEL (Current Setup)")
    print("="*80 + "\n")
    
    prompt = """What are the main challenges in training large language models?

Answer this based on general knowledge about deep learning."""
    
    print("📤 Prompt:")
    print(prompt)
    print("\n⏳ Generating response...\n")
    
    response = await ai_client.generate_text(prompt, mode="general")
    
    print("📥 Response:")
    print(response)
    print("\n" + "-"*80)
    
    # Check if response has reasoning
    has_structure = "<thinking>" in response or "First" in response or "step" in response.lower()
    print(f"\n✓ Response length: {len(response)} chars")
    print(f"{'✓' if has_structure else '✗'} Structured reasoning: {has_structure}")
    
    return response


async def test_cot_model_basic():
    """Test CoT model with explicit template"""
    print("\n" + "="*80)
    print("TEST 2: CHAIN-OF-THOUGHT MODEL (With Template)")
    print("="*80 + "\n")
    
    prompt = """What are the main challenges in training large language models?

Think step-by-step using this format:

<thinking>
1. What are the key areas to consider? (compute, data, optimization)
2. What specific problems exist in each area?
3. How do these problems relate to each other?
4. What's the current state of solutions?
</thinking>

<answer>
[Your detailed answer here]
</answer>
"""
    
    print("📤 Prompt:")
    print(prompt)
    print("\n⏳ Generating response...\n")
    
    response = await ai_client.generate_text(prompt, mode="general")
    
    print("📥 Response:")
    print(response)
    print("\n" + "-"*80)
    
    # Parse thinking and answer
    if "<thinking>" in response and "<answer>" in response:
        thinking_start = response.find("<thinking>") + len("<thinking>")
        thinking_end = response.find("</thinking>")
        answer_start = response.find("<answer>") + len("<answer>")
        answer_end = response.find("</answer>")
        
        thinking = response[thinking_start:thinking_end].strip()
        answer = response[answer_start:answer_end].strip()
        
        print("\n🧠 THINKING PROCESS:")
        print(thinking)
        print("\n💬 FINAL ANSWER:")
        print(answer)
        print(f"\n✓ Thinking tokens: ~{len(thinking.split())} words")
        print(f"✓ Answer tokens: ~{len(answer.split())} words")
    else:
        print("\n⚠ Warning: Model didn't use <thinking> tags")
        print("This might mean:")
        print("  1. You're still using the standard model")
        print("  2. The CoT model wasn't created yet")
        print("  3. The prompt template wasn't followed")
    
    return response


async def test_research_cot():
    """Test CoT with research-style prompt"""
    print("\n" + "="*80)
    print("TEST 3: RESEARCH QUERY WITH CHAIN-OF-THOUGHT")
    print("="*80 + "\n")
    
    prompt = """You are analyzing research papers to answer a question.

Question: How effective is chain-of-thought prompting for improving LLM reasoning?

Papers:
[1] "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
Authors: Wei et al. (2022)
Abstract: We explore how generating a chain of thought—a series of intermediate 
reasoning steps—significantly improves the ability of large language models to 
perform complex reasoning. On several benchmarks requiring multi-step reasoning, 
we show that chain of thought prompting substantially improves performance.

[2] "Large Language Models are Zero-Shot Reasoners"  
Authors: Kojima et al. (2022)
Abstract: We show that large language models are decent zero-shot reasoners 
by simply adding "Let's think step by step" before each answer. This simple 
prompt achieves results comparable to few-shot chain-of-thought prompting.

Think through your analysis:

<thinking>
1. Query Understanding: User wants to know about CoT effectiveness for LLM reasoning
2. Paper Relevance: Both papers [1,2] directly study CoT prompting
3. Evidence Analysis:
   - [1] shows CoT helps with complex reasoning via intermediate steps
   - [2] shows even simple "step by step" prompt works well
   - Both papers agree CoT improves reasoning performance
4. Synthesis: The evidence strongly supports CoT effectiveness
5. Confidence: High - both papers provide empirical evidence
</thinking>

---NARRATION---
[Your 2-3 sentence conversational explanation]

---CONTENT---
[Your formal synthesis with citations]

---END---
"""
    
    print("📤 Prompt (truncated):")
    print(prompt[:500] + "...\n")
    print("⏳ Generating response...\n")
    
    response = await ai_client.generate_text(prompt, mode="general")
    
    print("📥 Full Response:")
    print(response)
    print("\n" + "-"*80)
    
    # Parse all sections
    sections = {}
    if "<thinking>" in response:
        thinking_start = response.find("<thinking>") + len("<thinking>")
        thinking_end = response.find("</thinking>")
        sections['thinking'] = response[thinking_start:thinking_end].strip()
    
    if "---NARRATION---" in response:
        narr_start = response.find("---NARRATION---") + len("---NARRATION---")
        narr_end = response.find("---CONTENT---")
        sections['narration'] = response[narr_start:narr_end].strip()
    
    if "---CONTENT---" in response:
        content_start = response.find("---CONTENT---") + len("---CONTENT---")
        content_end = response.find("---END---")
        sections['content'] = response[content_start:content_end].strip()
    
    # Display parsed sections
    if sections:
        print("\n📊 PARSED OUTPUT:\n")
        
        if 'thinking' in sections:
            print("🧠 THINKING:")
            print(sections['thinking'])
            print()
        
        if 'narration' in sections:
            print("🗣️  NARRATION (for avatar):")
            print(sections['narration'])
            print()
        
        if 'content' in sections:
            print("📝 CONTENT (written):")
            print(sections['content'])
            print()
        
        print("✓ All sections parsed successfully!")
    else:
        print("\n⚠ Warning: Couldn't parse sections properly")
    
    return response


async def test_paper_ranking_cot():
    """Test paper ranking with reasoning"""
    print("\n" + "="*80)
    print("TEST 4: PAPER RANKING WITH REASONING")
    print("="*80 + "\n")
    
    prompt = """Rank this paper's relevance to the query on a scale of 0.0-1.0.

Query: "attention mechanisms in transformers"

Paper:
Title: "Attention Is All You Need"
Authors: Vaswani et al.
Year: 2017
Abstract: We propose the Transformer, a model architecture eschewing recurrence 
and relying entirely on an attention mechanism to draw global dependencies 
between input and output. The Transformer allows for significantly more 
parallelization and can reach a new state of the art in translation quality.

Analyze step-by-step:

<thinking>
1. Query keywords: "attention mechanisms", "transformers"
2. Paper topic: Introduces Transformer architecture based on attention
3. Alignment: Perfect match - this is THE foundational paper on the topic
4. Relevance: 1.0 - as relevant as it gets (original paper)
</thinking>

<score>
[0.0-1.0 number]
</score>

<reasoning>
[Brief 1 sentence explanation]
</reasoning>
"""
    
    print("📤 Prompt:")
    print(prompt)
    print("\n⏳ Generating response...\n")
    
    response = await ai_client.generate_text(prompt, mode="search")
    
    print("📥 Response:")
    print(response)
    print("\n" + "-"*80)
    
    # Extract score
    if "<score>" in response:
        score_start = response.find("<score>") + len("<score>")
        score_end = response.find("</score>")
        score_text = response[score_start:score_end].strip()
        
        try:
            score = float(score_text)
            print(f"\n📊 Extracted Score: {score}")
            
            if score >= 0.9:
                print("✓ High relevance detected correctly!")
            elif score >= 0.7:
                print("~ Moderate relevance")
            else:
                print("⚠ Low relevance - might need tuning")
        except:
            print(f"⚠ Could not parse score: {score_text}")
    
    return response


async def run_all_tests():
    """Run all CoT tests"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "CHAIN-OF-THOUGHT MODEL TESTS" + " "*30 + "║")
    print("╚" + "="*78 + "╝")
    
    print(f"\n📋 Configuration:")
    print(f"   Provider: {settings.llm_provider}")
    print(f"   Smart Model: {settings.ollama_model_smart}")
    print(f"   Search Model: {settings.ollama_model_search}")
    print(f"   Base URL: {settings.ollama_base_url}")
    
    try:
        # Run tests sequentially
        await test_standard_model()
        await asyncio.sleep(1)
        
        await test_cot_model_basic()
        await asyncio.sleep(1)
        
        await test_research_cot()
        await asyncio.sleep(1)
        
        await test_paper_ranking_cot()
        
        # Summary
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)
        
        print("\n📝 Next Steps:")
        print("   1. If <thinking> tags appeared: CoT is working!")
        print("   2. If no <thinking> tags: Create the CoT model first")
        print("      → cd backend/models")
        print("      → ollama create scholarmate-cot -f ScholarMate-CoT.Modelfile")
        print("   3. Update config.py to use 'scholarmate-cot'")
        print("   4. Re-run this test to verify")
        print("   5. Check CHAIN_OF_THOUGHT_GUIDE.md for full documentation")
        
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        print("\nPossible causes:")
        print("   - Ollama not running (start with: ollama serve)")
        print("   - Models not pulled (run: ollama pull llama3.2:3b)")
        print("   - Wrong model name in config.py")
        print(f"\nFull error: {e}")


if __name__ == "__main__":
    print("\n🚀 Starting Chain-of-Thought Model Tests...")
    asyncio.run(run_all_tests())
