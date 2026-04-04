
import arxiv
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("minimal_test")

def test_arxiv_minimal():
    print("Starting minimal arxiv test...", flush=True)
    try:
        client = arxiv.Client(page_size=5, delay_seconds=1, num_retries=1)
        search = arxiv.Search(query="paracetamol", max_results=5)
        print("Client and Search created. Iterating...", flush=True)
        
        for result in client.results(search):
            print(f"Got paper: {result.title}", flush=True)
            break
            
        print("Minimal test complete.", flush=True)
    except Exception as e:
        print(f"Minimal test failed: {e}", flush=True)

if __name__ == "__main__":
    test_arxiv_minimal()
