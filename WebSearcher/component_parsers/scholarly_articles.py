def parse_scholarly_articles(cmpt):
    """Parse a scholarly articles component

    These components contain links to academic articles via Google Scholar
    
    Args:
        cmpt (bs4 object): A scholarly_articles component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    data_list = []
    subs = cmpt.find_all('tr')[1].find_all('div')
    return [parse_article(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_article(sub, sub_rank=0):
    """Parse a scholarly articles subcomponent
    
    Args:
        sub (bs4 object): A scholarly articles subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'scholarly_articles', 'sub_rank':sub_rank}
    parsed['title'] = sub.text
    if sub.find('a'):
        parsed['url'] = sub.find('a').attrs['href']
        parsed['title'] = sub.find('a').text
        parsed['cite'] = sub.find('span').text.replace(' - \u200e', '')
    return parsed
