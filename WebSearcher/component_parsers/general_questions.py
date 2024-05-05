from .general import parse_general_results
from .people_also_ask import parse_people_also_ask

def parse_general_questions(cmpt):
    """Parse a General + People Also Ask hybrid component

    These components consist of a general result followed by a people also
    ask component with 3 subresults (questions).
    
    Args:
        cmpt (bs4 object): A latest from component
    
    Returns:
        dict : parsed result
    """

    result = parse_general_results(cmpt)
    questions = parse_people_also_ask(cmpt)
    result[0]['details'] = questions[0]['details']
    result[0]['type'] = 'general_questions'
    return result


