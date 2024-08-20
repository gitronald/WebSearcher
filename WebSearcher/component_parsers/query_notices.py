import copy
from ..models import BaseResult
from ..webutils import get_text, get_link

def parse_query_notices(cmpt):
    """Parse an image component
    
    Args:
        cmpt (bs4 object): an image component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """

    parsed = {}
    sub_type = classify_sub_type(cmpt)
    if sub_type == 'no_results_replacement':
        parsed = _parse_no_results_replacement(cmpt)
    elif sub_type == 'query_edit':
        parsed = _parse_query_edit(cmpt)
    elif sub_type == 'query_suggestion':
        parsed = _parse_query_suggestion(cmpt)

    result = BaseResult(
        type='query_notice',
        sub_type=sub_type,
        sub_rank=0,
        title=parsed.get('title', None),
        text=parsed.get('text', None),
    )
    return [result.model_dump()]


def classify_sub_type(cmpt):
    """Classify the sub-type of a query notice component"""
    text = cmpt.text
    if "No results found for" in text:
        return 'no_results_replacement'
    elif "Showing results for" in text:
        return 'query_edit'
    elif "Did you mean:" in text or "Are you looking for:" in text:
        return 'query_suggestion'
    return "unknown"


def _parse_no_results_replacement(cmpt):
    output = {"title": None, "text": None}

    cmpt = copy.copy(cmpt)
    no_results_div = cmpt.find('div', role='heading', attrs={'aria-level': '2'})
    if no_results_div:
        output['title'] = no_results_div.text.strip()
        no_results_div.extract()

    results_for_text = cmpt.find("div", {"class": "card-section"})
    if results_for_text:
        output['text'] = results_for_text.text.strip()

    return output

def _parse_query_edit(cmpt):
    output = {"title": None, "text": None}
    showing_results_span = cmpt.find('span', class_='gL9Hy')
    if showing_results_span:
        output['title'] = showing_results_span.text.strip()

    modified_query_link = cmpt.find('a', id='fprsl')
    if modified_query_link:
        modified_query = modified_query_link.text.strip()
        output['title'] += f" {modified_query}"

    search_instead_span = cmpt.find('span', class_='spell_orig')
    if search_instead_span:
        output['text'] = search_instead_span.text.strip()

    original_query_link = cmpt.find('a', class_='spell_orig')
    if original_query_link:
        original_query = original_query_link.text.strip()
        output['text'] += f" {original_query}"
    return output

def _parse_query_suggestion(cmpt):
    output = {"title": None, "text": None}

    # check in div and span with same class
    did_you_mean_span = cmpt.find('span', class_='gL9Hy')
    if did_you_mean_span:
        output['title'] = did_you_mean_span.text.strip()
    
    did_you_mean_div = cmpt.find('div', class_='gL9Hy')
    if did_you_mean_div:
        output['title'] = did_you_mean_div.text.strip()

    suggestion_links = cmpt.find_all('a', class_='gL9Hy')
    for suggestion_link in suggestion_links:
        suggested_query = get_text(suggestion_link)
        if suggested_query:
            output['text'] += suggested_query + " | "

    return output
