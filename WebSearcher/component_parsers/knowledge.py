def get_text(div):
    return '|'.join([d.get_text(separator=' ') for d in div if d.text])

def parse_knowledge_panel(cmpt, sub_rank=0):
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
        parsed['title'] = result.find('h3').text
        parsed['url'] = result.find('a')['href']
        parsed['cite'] = result.find('cite').text

    # Get details
    details = {}

    heading = cmpt.find('div', {'role':'heading'})
    details['heading'] = heading.text if heading else None

    # Get all text
    if cmpt.find('h2') and cmpt.find('h2').text == 'Featured snippet from the web':
        details['subtype'] = 'featured_snippet'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Unit Converter':
        details['subtype'] = 'unit_converter'
        span = cmpt.find_all(['span'])
        details['text'] = get_text(span) if span else None

    elif cmpt.find('h2') and cmpt.find('h2').text == 'Sports Results':
        details['subtype'] = 'sports'
        div = cmpt.find('div', {'class':'SwsxUd'})
        details['text'] = div.text if div else None

    else:
        details['subtype'] = 'panel'
        div = cmpt.find_all(['span','div','a'], text=True)
        details['text'] = get_text(div) if div else None

    # Get image
    img_div = cmpt.find('div', {'class':'img-brk'})
    details['img_url'] = img_div.find('a')['href'] if img_div else None
    parsed['details'] = details

    return [parsed]
