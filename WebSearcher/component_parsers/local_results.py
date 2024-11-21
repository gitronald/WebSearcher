from .. import utils
from .. import webutils

def parse_local_results(cmpt) -> list:
    """Parse a "Local Results" component

    These components contain an embedded map followed by vertically 
    stacked subcomponents for locations. These locations are typically 
    businesses relevant to the query.
    
    Args:
        cmpt (bs4 object): A local results component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('div', {'class': 'VkpGBb'})
    parsed_list = [parse_local_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    if parsed_list:

        # Set first non-empty header as sub_type (e.g. "Places" -> places)
        header_list = [
            webutils.get_text(cmpt, "h2", {"role":"heading"}),
            webutils.get_text(cmpt, 'div', {'aria-level':"2", "role":"heading"}),
        ]
        header_list = list(filter(None, header_list))
        if header_list:
            sub_type = str(header_list[0]).lower().replace(" ", "_")
            for parsed in parsed_list:
                parsed.update({'sub_type':sub_type})

        return parsed_list
    else:
        parsed = {
            'type':'local_results',
            'sub_rank':0,
            'text':webutils.get_text(cmpt, 'div', {'class': 'n6tePd'}) # No results message
        }
        return [parsed]

def parse_local_result(sub, sub_rank=0) -> dict:
    """Parse a "Local Results" subcomponent
    
    Args:
        sub (bs4 object): A local results subcomponent
    
    Returns:
        dict : parsed subresult
    """

    parsed = {'type':'local_results', 
              'sub_rank':sub_rank}
    parsed['title'] = webutils.get_text(sub, 'div', {'class':'dbg0pd'})

    # Extract URL
    links = [a.attrs['href'] for a in sub.find_all('a') if 'href' in a.attrs]
    links_text = [a.text.lower() for a in sub.find_all('a') if 'href' in a.attrs]
    links_dict = dict(zip(links_text, links))
    parsed['url'] = links_dict.get('website', None)

    # Extract text and label
    text = webutils.get_text(sub, 'div', {'class':'rllt__details'}, separator='<|>')
    label = webutils.get_text(sub, "span", {"class":"X0w5lc"})
    parsed['text'] = f"{text} <label>{label}</label>" if label else text
    parsed['details'] = parse_local_details(sub)

    return parsed


def parse_local_details(sub) -> dict:
    
    local_details = {}

    # Extract summary details
    detail_div = sub.find('span', {'class':'rllt__details'})
    detail_divs = detail_div.find_all('div') if detail_div else None

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
    return local_details