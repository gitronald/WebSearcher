import WebSearcher as ws
se = ws.SearchEngine()                     # 1. Initialize collector
se.launch_chromedriver(headless = False)   # 2. Launch undetected chromedriver window
se.search('immigration news')              # 2. Conduct a search
se.parse_results()                         # 3. Parse search results
se.save_serp(append_to='serps.json')       # 4. Save HTML and metadata
se.save_results(append_to='results.json')  # 5. Save parsed results
