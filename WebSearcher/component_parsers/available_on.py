def parse_available_on(cmpt, sub_rank=0):
    """Parse an available component

    These components contain a carousel of thumbnail images with links to
    entertainment relevant to query 
    
    Args:
        cmpt (bs4 object): An available on component
    
    Returns:
        dict : parsed component
    """
    parsed = {'type':'available_on', 'sub_rank':sub_rank}

    parsed['title'] = cmpt.find('span', {'class':'GzssTd'}).text

    details = []
    options = cmpt.find_all('div', {'class':'kno-fb-ctx'})
    for o in options:
        option = {}
        option['title'] = o.find('div', {'class':'i3LlFf'}).text
        option['cost']  = o.find('div', {'class':'V8xno'}).text
        option['url']   = o.find('a')['href']
        details.append(option)
    parsed['details'] = details
    return [parsed]
