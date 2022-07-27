def parse_shopping_ads(cmpt):
    """Parse all shopping ads from a shopping ads carousel

    Args:
        cmpt (bs4 object): a shopping ads component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """

    subs = cmpt.find_all('div', {'class':'mnr-c pla-unit'})
    return [parse_shopping_ad(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_shopping_ad(sub, sub_rank=0):
    """Parse a shopping ad subcomponent
    
    Args:
        sub (bs4 object): a shopping ad subcomponent
    
    Returns:
        dict : parsed subresult
    """

    parsed = {'type': 'shopping_ads', 'sub_rank': sub_rank}

    card = sub.find('a', {'class': 'clickable-card'})
    if card:
        parsed['url'] = card['href']
        parsed['title'] = card['aria-label']
    return parsed

