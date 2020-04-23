def parse_view_more_news(cmpt):
    """Parse a "View more news" component

    These components are highly similar to the vertically stacked Top Stories 
    and Latest from results, but include a news icon in the top left.
    
    Args:
        cmpt (bs4 object): A local results component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """

    if cmpt.find('div', {'class':'qmv19b'}):
        subs = cmpt.find('div', {'class':'qmv19b'}).children
    elif cmpt.find('g-scrolling-carousel'):
        subs = cmpt.find('g-scrolling-carousel').find_all('g-inner-card')
    return [parse_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_sub(sub, sub_rank=0):
    """Parse a "View more news" subcomponent
    
    Args:
        sub (bs4 object): A view more news subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'view_more_news', 'sub_rank':sub_rank}
    parsed['title'] = sub.find('div', {'class','jBgGLd'}).text
    parsed['url'] = sub.find('a').attrs['href']

    if sub.find('span', {'class':'wqg8ad'}):
        parsed['cite'] = sub.find('span', {'class':'wqg8ad'}).text
    elif sub.find('cite'):
        parsed['cite'] = sub.find('cite').text

    if sub.find('span', {'class':'FGlSad'}):
        parsed['timestamp'] = sub.find('span', {'class':'FGlSad'}).text
    elif sub.find('span', {'class':'f'}):
        parsed['timestamp'] = sub.find('span', {'class':'f'}).text

    parsed['img_url'] = get_img_url(sub)
    return parsed

def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']