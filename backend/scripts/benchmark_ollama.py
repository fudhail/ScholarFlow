"""
Ollama Performance Benchmark Script
Tests speed improvements before and after optimization
"""
import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ai_client import ai_client


async def benchmark_sequential():
    """Test sequential request processing (old method)"""
    prompts = [
        "Summarize quantum computing in 50 words",
        "What is machine learning?",
        "Explain neural networks briefly",
        "Define artificial intelligence",
        "What are large language models?"
    ]
    
    print("\n" + "="*80)
    print("BENCHMARK: Sequential Requests")
    print("="*80)
    
    start = time.time()
    results = []
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nRequest {i}/{len(prompts)}: {prompt[:50]}...")
        request_start = time.time()
        
        result = await ai_client.generate_text(prompt, use_flash=True)
        
        request_time = time.time() - request_start
        results.append(result)
        print(f"  ✅ Completed in {request_time:.2f}s")
    
    total_time = time.time() - start
    avg_time = total_time / len(prompts)
    
    print("\n" + "-"*80)
    print(f"Total Time: {total_time:.2f}s")
    print(f"Average per Request: {avg_time:.2f}s")
    print(f"Requests per Second: {len(prompts)/total_time:.2f}")
    
    return total_time, avg_time


async def benchmark_batch():
    """Test batch/parallel request processing (optimized method)"""
    prompts = [
        "Summarize quantum computing in 50 words",
        "What is machine learning?",
        "Explain neural networks briefly",
        "Define artificial intelligence",
        "What are large language models?"
    ]
    
    print("\n" + "="*80)
    print("BENCHMARK: Batch/Parallel Requests")
    print("="*80)
    
    print(f"\nProcessing {len(prompts)} requests in parallel...")
    
    start = time.time()
    results = await ai_client.generate_batch(prompts, use_flash=True)
    total_time = time.time() - start
    
    avg_time = total_time / len(prompts)
    
    print("\n" + "-"*80)
    print(f"Total Time: {total_time:.2f}s")
    print(f"Average per Request: {avg_time:.2f}s")
    print(f"Requests per Second: {len(prompts)/total_time:.2f}")
    
    return total_time, avg_time


async def benchmark_model_comparison():
    """Compare flash (fast) vs smart (quality) model speeds"""
    prompt = "Explain quantum entanglement in 100 words"
    
    print("\n" + "="*80)
    print("BENCHMARK: Model Speed Comparison")
    print("="*80)
    
    # Test flash model (llama3.2:1b)
    print("\n🚀 Testing FLASH model (llama3.2:1b - optimized for speed)...")
    flash_start = time.time()
    flash_result = await ai_client.generate_text(prompt, use_flash=True)
    flash_time = time.time() - flash_start
    
    print(f"  Flash Model: {flash_time:.2f}s")
    print(f"  Response length: {len(flash_result)} chars")
    
    # Small delay between tests
    await asyncio.sleep(1)
    
    # Test smart model (scholarmate - 3B)
    print("\n🎓 Testing SMART model (scholarmate - optimized for quality)...")
    smart_start = time.time()
    smart_result = await ai_client.generate_text(prompt, use_flash=False)
    smart_time = time.time() - smart_start
    
    print(f"  Smart Model: {smart_time:.2f}s")
    print(f"  Response length: {len(smart_result)} chars")
    
    # Calculate speedup
    speedup = smart_time / flash_time
    
    print("\n" + "-"*80)
    print(f"Flash model is {speedup:.2f}x faster than Smart model")
    print(f"Time saved: {smart_time - flash_time:.2f}s")
    
    return flash_time, smart_time


async def benchmark_first_request_latency():
    """Test cold start vs warm start latency"""
    prompt = "What is deep learning?"
    
    print("\n" + "="*80)
    print("BENCHMARK: First Request Latency (Keep-Alive Test)")
    print("="*80)
    
    print("\n🔥 First request (model may need loading)...")
    first_start = time.time()
    first_result = await ai_client.generate_text(prompt, use_flash=True)
    first_time = time.time() - first_start
    print(f"  First request: {first_time:.2f}s")
    
    await asyncio.sleep(0.5)
    
    print("\n⚡ Second request (model should be cached in memory)...")
    second_start = time.time()
    second_result = await ai_client.generate_text(prompt, use_flash=True)
    second_time = time.time() - second_start
    print(f"  Second request: {second_time:.2f}s")
    
    improvement = ((first_time - second_time) / first_time) * 100
    
    print("\n" + "-"*80)
    print(f"Keep-alive improvement: {improvement:.1f}% faster on warm start")
    print(f"Time saved: {first_time - second_time:.2f}s")
    
    if improvement > 50:
        print("✅ Keep-alive is working well!")
    else:
        print("⚠️  Keep-alive may need tuning")
    
    return first_time, second_time


async def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "OLLAMA PERFORMANCE BENCHMARK" + " "*30 + "║")
    print("╚" + "="*78 + "╝")
    print("\n")
    print("Testing Ollama optimization improvements...")
    print("This will take about 2-3 minutes.\n")
    
    try:
        # Benchmark 1: Model comparison
        flash_time, smart_time = await benchmark_model_comparison()
        
        # Benchmark 2: Keep-alive test
        first_time, second_time = await benchmark_first_request_latency()
        
        # Benchmark 3: Sequential vs parallel
        seq_total, seq_avg = await benchmark_sequential()
        batch_total, batch_avg = await benchmark_batch()
        
        # Calculate improvements
        parallel_speedup = seq_total / batch_total
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("\n📊 Performance Improvements:")
        print(f"  • Flash model: {smart_time/flash_time:.2f}x faster than Smart model")
        print(f"  • Keep-alive: {((first_time - second_time) / first_time) * 100:.1f}% latency reduction")
        print(f"  • Parallel requests: {parallel_speedup:.2f}x faster than sequential")
        print(f"\n⚡ Overall System Speed:")
        print(f"  • Average response time (flash): {seq_avg:.2f}s")
        print(f"  • Parallel throughput: {5/batch_total:.2f} requests/second")
        
        # Expected vs actual
        print(f"\n🎯 Optimization Goals:")
        if seq_avg < 1.0:
            print(f"  ✅ Target: <1s per request - ACHIEVED ({seq_avg:.2f}s)")
        else:
            print(f"  ⚠️  Target: <1s per request - Current: {seq_avg:.2f}s")
        
        if parallel_speedup > 2.5:
            print(f"  ✅ Parallel speedup: >2.5x - ACHIEVED ({parallel_speedup:.2f}x)")
        else:
            print(f"  ⚠️  Parallel speedup: >2.5x - Current: {parallel_speedup:.2f}x")
        
        print("\n✅ Benchmark complete!")
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
