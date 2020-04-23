def parse_twitter_result(cmpt, sub_rank=0):
    """Parse a Twitter single result component

    These components look like general components, but link to a Twitter account
    and sometimes have a tweet in the summary.
    
    Args:
        cmpt (bs4 object): A twitter cards component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """    
    parsed = {'type':'twitter_result', 'sub_rank':sub_rank}

    # Header
    header = cmpt.find('div', {'class':'DOqJne'})
    if header:
        title = header.find('g-link')
        # Get title
        if title:
            parsed['title'] = title.find('a').text
            parsed['url'] = title.find('a')['href']

        # Get citation
        cite = header.find('cite')
        if cite:
            parsed['cite'] = cite.text
    
    # Get snippet text, timestamp, and tweet url
    body, timestamp_url = cmpt.find('div', {'class':'tw-res'}).children
    parsed['text'] = body.text
    parsed['timestamp'] = timestamp_url.find('span').text
    parsed['details'] = timestamp_url.find('a')['href']
    return [parsed]