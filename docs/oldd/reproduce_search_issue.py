
import asyncio
import logging
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Configure logging to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)

logger = logging.getLogger("reproduce_script")

from app.services.arxiv_client import arxiv_client
from app.services.paper_search import search_all_sources, search_arxiv_wrapper

async def test_search():
    query = "paracetamol"
    print(f"Testing search with query: {query}", flush=True)

    # Test 1: Direct ArxivClient search
    print("--- Test 1: Direct ArxivClient search ---", flush=True)
    try:
        # Wrap in generic timeout to catch hang
        results = await asyncio.to_thread(arxiv_client.search, query, max_results=5)
        print(f"Direct ArxivClient returned {len(results)} results", flush=True)
        if results:
            print(f"First result title: {results[0]['title']}", flush=True)
    except Exception as e:
        print(f"Direct ArxivClient search failed: {e}", flush=True)

    # Test 2: search_arxiv_wrapper
    print("\n--- Test 2: search_arxiv_wrapper ---", flush=True)
    try:
         results = await asyncio.to_thread(search_arxiv_wrapper, query, max_results=5)
         print(f"search_arxiv_wrapper returned {len(results)} results", flush=True)
    except Exception as e:
        print(f"search_arxiv_wrapper failed: {e}", flush=True)

    # Test 3: search_all_sources
    print("\n--- Test 3: search_all_sources ---", flush=True)
    try:
        results = await asyncio.to_thread(search_all_sources, query, max_results_per_source=5)
        print(f"search_all_sources returned {len(results)} results", flush=True)
    except Exception as e:
        print(f"search_all_sources failed: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_search())
