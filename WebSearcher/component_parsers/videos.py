def parse_videos(cmpt):
    """Parse a videos component

    These components contain links to videos, frequently to YouTube.
    
    Args:
        cmpt (bs4 object): A videos component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('g-inner-card')
    return [parse_video(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_video(sub, sub_rank=0):
    """Parse a videos subcomponent
    
    Args:
        sub (bs4 object): A video subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'videos', 'sub_rank':sub_rank}
    parsed['url'] = sub.find('a')['href']
    parsed['title'] = sub.find('div', {'role':'heading'}).text

    text_div, citetime_div = sub.find_all('div',{'class':'MjS0Lc'})
    parsed['text'] = text_div.text if text_div else None

    if citetime_div:
        # Sometimes there is only a cite
        citetime = list(citetime_div.find('div',{'class':'zECGdd'}).children)
        if len(citetime) == 2:
            cite, timestamp = citetime       
            parsed['cite'] = cite.text
            parsed['timestamp'] = timestamp.replace(' - ', '')
        else:
            parsed['cite'] = citetime[0].text

    parsed['details'] = {} 
    parsed['details']['img_url'] = get_img_url(sub)
    return parsed

def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']
