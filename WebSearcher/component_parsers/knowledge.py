from .. import webutils
from .general import parse_general_result


def parse_knowledge_panel(cmpt, sub_rank=0) -> list:
    """Parse the Knowledge Box
    
    Args:
        cmpt (bs4 object): a knowledge component
    
    Returns:
        list: Return parsed dictionary in a list
    """
    parsed = {'type':'knowledge', 'sub_rank':sub_rank}

    # Get embedded result if it exists
    result = cmpt.find('div', {'class':'rc'})
    if result:
        parsed['title'] = webutils.get_text(result, 'h3')
        parsed['url'] = webutils.get_link(result)
        parsed['cite'] = webutils.get_text(result, 'cite')

    parsed['text'] = webutils.get_text(cmpt, "div", {"role":"heading", "aria-level":"3"})

    # Get details
    details = {}

    heading = cmpt.find('div', {'role':'heading'})
    details['heading'] = heading.text if heading else None

    alinks = cmpt.find_all('a')
    if alinks:
        details['urls'] = [
            parse_alink(a) 
            for a in alinks 
            if 'href' in a.attrs and a['href'] != '#'
        ] 

    # Get all text
    if cmpt.find("div", {"class": "Fzsovc"}):
        parsed['sub_type'] = 'ai_overview'
    elif cmpt.find("div", {"class":"pxiwBd"}):
        parsed['sub_type'] = 'featured_results'
    elif (
        cmpt.find('h2') and cmpt.find('h2').text == 'Featured snippet from the web' or 
        cmpt.find('div', {'class':'answered-question'})
    ):
        parsed['sub_type'] = 'featured_snippet'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

        # General component with no abstract
        if cmpt.find('div', {'class':'g'}):
            parsed_general = parse_general_result(cmpt.find('div', {'class':'g'}))
            parsed_general = {k:v for k,v in parsed_general.items() if k in {'title', 'url', 'cite'}}
            parsed.update(parsed_general)


    elif cmpt.find('h2') and cmpt.find('h2').text == 'Unit Converter':
        parsed['sub_type'] = 'unit_converter'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Sports Results':
        parsed['sub_type'] = 'sports'
        div = cmpt.find('div', {'class':'SwsxUd'})
        details['text'] = div.text if div else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Weather Result':
        parsed['sub_type'] = 'weather'

    elif (
        cmpt.find('h2') and cmpt.find('h2').text == 'Finance Results' or
        cmpt.find('div', {'id':'knowledge-finance-wholepage__entity-summary'})
    ):
        parsed['sub_type'] = 'finance'

    elif cmpt.find('div', {'role':'button'}) and cmpt.find('div', {'role':'button'}).text == 'Dictionary':
        parsed['sub_type'] = 'dictionary'
        span_first = cmpt.find('span', {'jsslot':''})
        if span_first:
            span = span_first.find_all('span')
            details['text'] = get_text(span).split('Translate')[0] if span else None

    elif (
        cmpt.find('h2') and cmpt.find('h2').text == 'Translation Result' or
        cmpt.find('h2') and cmpt.find('h2').text == 'Resultado de traducción'
    ):
        parsed['sub_type'] = 'translate'
        span = cmpt.find_all('span')
        details['text'] = get_text(span).split('Community Verified')[0] if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Calculator Result':
        parsed['sub_type'] = 'calculator'

    elif details['heading'] == '2020 US election results':
        parsed['sub_type'] = 'election'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    else:
        parsed['sub_type'] = 'panel'
        div = cmpt.find_all(['span','div','a'], string=True)
        details['text'] = get_text(div) if div else None

        text_divs = cmpt.find_all("div", {"class":"sinMW"})
        text_list = [webutils.get_text(div) for div in text_divs]
        parsed["text"] = "<|>".join(text_list) if text_list else None
        parsed["title"] = webutils.get_text(cmpt, "div", {"class": ["ZbhV9d", "HdbW6"]})
        # parsed["title"] = webutils.get_text(cmpt, "div", {"class":"HdbW6"}) if not parsed["title"] else parsed["title"]

    # Get image
    img_div = cmpt.find('div', {'class':'img-brk'})
    details['img_url'] = img_div.find('a')['href'] if img_div else None
    parsed['details'] = details

    return [parsed]

def get_text(div):
    return '|'.join([d.get_text(separator=' ') for d in div if d.text])

def parse_alink(a):
    return {'url': a['href'], 'text': a.get_text('|')}
