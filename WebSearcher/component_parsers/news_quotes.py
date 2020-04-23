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
    title, meta = result.children
    cite, timestamp = meta.children
    parsed['text'] = quote.text
    parsed['title'] = title.text
    parsed['url'] = title['href']
    parsed['cite'] = cite.text
    parsed['timestamp'] = timestamp.text
    return parsed
