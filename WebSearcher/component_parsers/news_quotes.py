def parse_news_quotes(cmpt):
    """Parse a "Quotes in the News" component
    
    Args:
        cmpt (bs4 object): a news quotes component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('g-inner-card')
    return [parse_news_quote(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_news_quote(sub, sub_rank=0):
    """Parse a "Quotes in the News" subcomponent
    
    Args:
        sub (bs4 object): a news quotes subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'news_quotes', 'sub_rank':sub_rank}
    children = list(sub.children)

    if len(children) == 1: # Unfold nested div
        children = list(children[0].children)
    if len(children) == 2:
        quote, result = children
    else: # Remove dummy div in middle
        quote, _, result = children

    # legacy parsing
    if (len(list(result.children)) == 2):
        title, meta = result.children
        cite, timestamp = meta.children
        parsed['title'] = title.text
        parsed['url'] = title['href']
        parsed['cite'] = cite.text
        parsed['timestamp'] = timestamp.text
    else:
        all_result = list(result.children)
        title = all_result[1]
        cite  = all_result[0]
        timestamp = all_result[2] # dates are no relative vs absolute
        parsed['title'] = title.div.text
        parsed['url'] = title['href']
        parsed['cite'] = cite.span.text
        parsed['timestamp'] = timestamp.div.text
        
    parsed['text'] = quote.text 
    
    return parsed

