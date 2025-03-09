import WebSearcher as ws

#chromedriver_path = "/opt/homebrew/Caskroom/chromedriver/133.0.6943.53"

se = ws.SearchEngine()                     # 1. Initialize collector
se.launch_chromedriver(headless=False,     # 2. Launch undetected_chromedriver window 
                       use_subprocess=False,
                       version_main=133)   
se.search('immigration news')              # 2. Conduct a search
se.parse_results()                         # 3. Parse search results
se.save_serp(append_to='serps.json')       # 4. Save HTML and metadata
se.save_results(append_to='results.json')  # 5. Save parsed results

#import pandas as pd
#df = pd.DataFrame(se.results)                   # 6. Display results in a pandas dataframe