from .. import webutils
from ..models import BaseResult

def parse_searches_related(cmpt, sub_rank=0):
    """Parse a one or two column list of related search queries"""

    parsed = {'type':'searches_related', 
              'sub_rank':sub_rank}

    # Set first non-empty header as sub_type (e.g. "Additional searches" -> additional_searches)
    header_list = [
        webutils.get_text(cmpt, "h2", {"role":"heading"}),
        webutils.get_text(cmpt, 'div', {'aria-level':"2", "role":"heading"}),
    ]
    header_list = list(filter(None, header_list))
    parsed['sub_type'] = str(header_list[0]).lower().replace(" ", "_") if header_list else None

    output_list = []

    # Classic search query suggestions
    subs = webutils.find_all_divs(cmpt, 'a', {'class':'k8XOCe'})
    text_list = [sub.text for sub in subs]
    output_list.extend(filter(None, text_list))

    # Curated list (e.g. song names)
    subs = webutils.find_all_divs(cmpt, 'div', {'class':'EASEnb'})
    text_list = [sub.text for sub in subs]
    output_list.extend(filter(None, text_list))
    
    # Accordion list
    if cmpt.find('explore-desktop-accordion'):
        subs = webutils.find_all_divs(cmpt, 'div', {'class':'JXa4nd'})
        text_list = [webutils.get_text(sub, 'div', {'class':'Cx1ZMc'}) for sub in subs]
        output_list.extend(filter(None, text_list))

    parsed['text'] = '<|>'.join(output_list)
    parsed['details'] = output_list
    return [BaseResult(**parsed).model_dump()]

