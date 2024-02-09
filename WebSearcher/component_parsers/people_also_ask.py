from .. import webutils
from ..models import BaseResult

def parse_people_also_ask(cmpt, sub_rank=0):
    """Parse a "People Also Ask" component

    These components contain a list of questions, which drop down to reveal  
    summarized information and/or general component results. However, browser  
    automation is required to preserve the information in the dropdown, which  
    only loads after a subcomponent is clicked.
    
    Args:
        cmpt (bs4 object): A "People Also Ask" component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """

    # questions = cmpt.find_all('g-accordion-expander')
    # questions = cmpt.find('section').find_all('div', {'class':'yTrXHe'})
    questions = cmpt.find_all("div", {"class":"related-question-pair"})
    details = [parse_question(q) for q in questions] if questions else None

    parsed = BaseResult(
        type='people_also_ask',
        sub_rank=sub_rank,
        text="<|>".join(details) if details else None,
        details=details,
    )

    return [parsed.model_dump()]


def parse_question(question):
    """Parse an individual question in a "People Also Ask" component"""

    # Get title
    title_divs = [
        question.find('div', {'class':'rc'}),
        question.find('div', {'class':'yuRUbf'}),
        question.find('div', {'class':'iDjcJe'}),  # 2023-01-01
        question.find('div', {'class':'JlqpRe'}),  # 2023-11-16
    ]
    for title_div in filter(None, title_divs):
        text = webutils.get_text(title_div)
    return text if text else None
