from .. import webutils 

def parse_map_results(cmpt, sub_rank=0) -> list:
    """Parse a "Map Results" component

    These components contain an embedded map that is not followed by 
    map results.
    
    Args:
        cmpt (bs4 object): A map results component
    
    Returns:
        dict : parsed result
    """
    return [{
        'type': 'map_results',
        'sub_rank': sub_rank,
        'title': get_title(cmpt)
    }]

def get_title(cmpt):
    # return webutils.get_text(cmpt, 'div', {'class':'desktop-title-content'})
    return webutils.get_text(cmpt, 'div', {'class':'aiAXrc'})