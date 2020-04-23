def parse_map_results(cmpt, sub_rank=0):
    """Parse a "Map Results" component

    These components contain an embedded map that is not followed by 
    map results.
    
    Args:
        cmpt (bs4 object): A map results component
    
    Returns:
        dict : parsed result
    """
    parsed = {'type':'map_results', 'sub_rank':sub_rank}
    details = {}

    title_div = cmpt.find('div', {'class':'desktop-title-content'})
    details['title'] = title_div.text if title_div else None

    subtitle_span = cmpt.find('span', {'class':'desktop-title-subcontent'})
    details['subtitle'] = subtitle_span.text if subtitle_span else None

    img = cmpt.find('img', {'id':'lu_map'})
    details['img_title'] = img.attrs['title'] if 'title' in img.attrs else None
    parsed['details'] = details
    return [parsed]