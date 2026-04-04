
import requests
import logging
import sys
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("requests_test")

def test_arxiv_requests():
    print("Starting requests-based arxiv test...", flush=True)
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": "all:paracetamol",
        "start": 0,
        "max_results": 5
    }
    
    try:
        print(f"Sending request to {url}...", flush=True)
        response = requests.get(url, params=params, timeout=10)
        print(f"Response status: {response.status_code}", flush=True)
        
        if response.status_code == 200:
            content = response.text
            print(f"Response length: {len(content)}", flush=True)
            # Parse XML
            root = ET.fromstring(content)
            # Namespace map
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text
                print(f"Paper: {title}", flush=True)
        else:
            print("Request failed.", flush=True)
            
    except Exception as e:
        print(f"Requests test failed: {e}", flush=True)

if __name__ == "__main__":
    test_arxiv_requests()
