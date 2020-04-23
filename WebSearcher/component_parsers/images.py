def parse_images(cmpt):
    """Parse an image component
    
    Args:
        cmpt (bs4 object): an image component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('img')
    return [parse_img(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_img(sub, sub_rank=0):
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'images', 'sub_rank':sub_rank}
    if 'title' in sub.attrs:
        # Hacky, 'src' is always the same though
        parsed['url'] = sub['title'] 
    return parsed
