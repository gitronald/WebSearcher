from ..webutils import get_text, get_link

def parse_twitter_result(cmpt, sub_rank=0) -> list:
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
    parsed['text'] = get_text(body)
    parsed['timestamp'] = get_text(timestamp_url, 'span')
    parsed['details'] = get_link(timestamp_url)
    return [parsed]