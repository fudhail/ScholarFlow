"""Test ArXiv API directly to diagnose search issues"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import sys
import time

def test_arxiv_search(query: str):
    """Test ArXiv search with detailed logging and rate limit handling"""
    print(f"\n{'='*60}")
    print(f"Testing ArXiv API with query: '{query}'")
    print(f"{'='*60}\n")
    
    try:
        # Construct API URL
        base_url = 'http://export.arxiv.org/api/query?'
        params = {
            'search_query': query,
            'start': 0,
            'max_results': 5,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }
        
        query_string = urllib.parse.urlencode(params)
        url = base_url + query_string
        
        print(f"1️⃣  API URL: {url}\n")
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_count = 0
        data = None
        
        while retry_count < max_retries:
            # Make request
            print(f"2️⃣  Making HTTP request (attempt {retry_count + 1}/{max_retries})...")
            try:
                with urllib.request.urlopen(url, timeout=15) as response:
                    data = response.read()
                    break  # Success
                    
            except urllib.error.HTTPError as http_err:
                if http_err.code == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # 2s, 4s, 8s
                        print(f"⚠️  Rate limit (429). Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ Rate limit exceeded after {max_retries} retries")
                        print("\n💡 Tip: ArXiv limits requests to ~1 every 3 seconds")
                        return False
                else:
                    print(f"❌ HTTP Error {http_err.code}: {http_err}")
                    return False
        
        if data is None:
            print("❌ Failed to retrieve data")
            return False
        
        print(f"✓ Received {len(data)} bytes\n")
        
        # Parse XML
        print("3️⃣  Parsing XML response...")
        root = ET.fromstring(data)
        
        # ArXiv API uses Atom namespace
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', ns)
        print(f"✓ Found {len(entries)} papers\n")
        
        if len(entries) == 0:
            print("⚠️  No papers found!")
            print("\nPossible reasons:")
            print("  - Query is too specific")
            print("  - Query uses unsupported syntax")
            print("  - ArXiv API has no matches")
            return False
        
        # Display results
        print(f"{'='*60}")
        print("RESULTS:")
        print(f"{'='*60}\n")
        
        for i, entry in enumerate(entries, 1):
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None else "No title"
            title = ' '.join(title.split())  # Normalize whitespace
            
            authors_elems = entry.findall('atom:author', ns)
            authors = []
            for author in authors_elems:
                name_elem = author.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)
            
            id_elem = entry.find('atom:id', ns)
            arxiv_id = id_elem.text.split('/')[-1] if id_elem is not None else "Unknown"
            
            print(f"{i}. {title}")
            print(f"   Authors: {', '.join(authors[:3])}{' et al.' if len(authors) > 3 else ''}")
            print(f"   arXiv ID: {arxiv_id}\n")
        
        print(f"{'='*60}")
        print("✅ ArXiv API is working correctly!")
        print(f"{'='*60}\n")
        return True
        
    except urllib.error.URLError as e:
        print(f"❌ Network Error: {e}")
        print("\nThis could mean:")
        print("  - No internet connection")
        print("  - Firewall blocking ArXiv")
        print("  - ArXiv API is down")
        return False
    except ET.ParseError as e:
        print(f"❌ XML Parsing Error: {e}")
        print("\nReceived invalid XML from ArXiv")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test queries
    test_queries = [
        "attention is all you need",
        "chain of thought prompting",
        "How does Chain-of-Thought prompting improve reasoning?"
    ]
    
    # Use query from command line if provided
    if len(sys.argv) > 1:
        test_queries = [' '.join(sys.argv[1:])]
    
    all_passed = True
    for query in test_queries:
        result = test_arxiv_search(query)
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check network connection and ArXiv availability.")
        sys.exit(1)
