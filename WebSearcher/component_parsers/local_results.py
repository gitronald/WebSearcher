from .. import utils

def parse_local_results(cmpt):
    """Parse a "Local Results" component

    These components contain an embedded map followed by vertically 
    stacked subcomponents for locations. These locations are typically 
    businesses relevant to the query.
    
    Args:
        cmpt (bs4 object): A local results component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('div', {'class':'VkpGBb'})
    return [parse_local_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_local_result(sub, sub_rank=0):
    """Parse a "Local Results" subcomponent
    
    Args:
        sub (bs4 object): A local results subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'local_results', 'sub_rank':sub_rank}
    local_details = {}

    parsed['title'] = sub.find('div', {'class','dbg0pd'}).text

    # Extract summary details
    detail_divs = sub.find('span', {'class':'rllt__details'}).find_all('div')

    # Extract rating and location type
    if detail_divs:
        rating_div = detail_divs[0]
        rating = rating_div.find('span', {'class':'BTtC6e'})
        if rating: 
            local_details['rating'] = float(rating.text)
            n_reviews = utils.get_between_parentheses(rating_div.text).replace(',','')
            local_details['n_reviews'] = int(n_reviews)
        local_details['loc_label'] = rating_div.text.split('·')[-1].strip()

    # Extract contact details
    if len(detail_divs) > 1:
        contact_div = detail_divs[1]
        local_details['contact'] = contact_div.text

    # Extract various links
    links = [a.attrs['href'] for a in sub.find_all('a') if 'href' in a.attrs]
    links_text = [a.text.lower() for a in sub.find_all('a') if 'href' in a.attrs]
    links_dict = dict(zip(links_text, links))
    local_details.update(links_dict)
    parsed['details'] = local_details

    if 'website' in links_dict:
        parsed['url'] = links_dict['website']
    
    return parsed