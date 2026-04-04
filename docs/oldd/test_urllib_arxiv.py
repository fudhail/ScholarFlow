
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import sys

# Flush stdout to ensure we see output
print("Starting urllib test...", flush=True)

try:
    base_url = 'http://export.arxiv.org/api/query?'
    params = {
        'search_query': 'all:paracetamol',
        'start': 0,
        'max_results': 5
    }
    
    query_string = urllib.parse.urlencode(params)
    url = base_url + query_string
    
    print(f"Calling {url}...", flush=True)
    
    with urllib.request.urlopen(url, timeout=10) as response:
        data = response.read()
        
    print(f"Received {len(data)} bytes.", flush=True)
    
    root = ET.fromstring(data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    for entry in root.findall('atom:entry', ns):
        title = entry.find('atom:title', ns).text
        print(f"Paper: {title}", flush=True)
        
    print("Test complete.", flush=True)
    
except Exception as e:
    print(f"Test failed: {e}", flush=True)
