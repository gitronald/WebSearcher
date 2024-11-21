from .general import parse_general_results
from .people_also_ask import parse_people_also_ask

def parse_general_questions(cmpt) -> list:
    """Parse a General + People Also Ask hybrid component

    These components consist of a general result followed by a people also
    ask component with 3 subresults (questions).
    
    Args:
        cmpt (bs4 object): A latest from component
    
    Returns:
        dict : parsed result
    """

    parsed_list_general = parse_general_results(cmpt)
    parsed_list_ppa = parse_people_also_ask(cmpt)
    parsed_list_general[0]['details'] = parsed_list_ppa[0].get('details', None)
    parsed_list_general[0]['type'] = 'general_questions'
    return parsed_list_general
