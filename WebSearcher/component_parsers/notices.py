import copy
from ..models import BaseResult
from ..webutils import get_text, get_link

def parse_notices(cmpt) -> list:
    """Parse a query notices component"""

    parsed = {}
    sub_type = classify_sub_type(cmpt)
    if sub_type == 'query_edit':
        parsed = _parse_query_edit(cmpt)
    elif sub_type == 'query_edit_no_results':
        parsed = _parse_no_results_replacement(cmpt)
    elif sub_type == 'query_suggestion':
        parsed = _parse_query_suggestion(cmpt)
    elif sub_type == 'location_choose_area':
        parsed = _parse_location_choose_area(cmpt)
    elif sub_type == 'location_use_precise_location':
        parsed = _parse_location_use_precise_location(cmpt)

    result = BaseResult(
        type='notice',
        sub_type=sub_type,
        sub_rank=0,
        title=parsed.get('title', None),
        text=parsed.get('text', None),
    )
    return [result.model_dump()]


def classify_sub_type(cmpt) -> str:
    """Classify the sub-type of a query notice component"""
    text = cmpt.text
    
    query_edit_check_list = ["Showing results for", "Including results for"]
    query_suggestion_check_list = [
        "Did you mean:", 
        "Are you looking for:", 
        "Search for this instead?", 
        "Did you mean to search for:", 
        "Search instead for:",
    ]

    if any(check_text in text for check_text in query_edit_check_list):
        return 'query_edit'
    elif "No results found for" in text:
        return 'query_edit_no_results'
    elif any(check_text in text for check_text in query_suggestion_check_list):
        return 'query_suggestion'
    elif "Results for" in text and "Choose area" in text:
        return 'location_choose_area'
    elif "Results for" in text and "Use precise location" in text:
        return 'location_use_precise_location'
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
    suggested_queries = [get_text(suggestion_link) for suggestion_link in suggestion_links if suggestion_link]
    output['text'] = '<|>'.join(suggested_queries)

    return output

def _parse_location_choose_area(cmpt):
    output = {"title": None, "text": None}
    
    # Extract the main heading
    heading = cmpt.find('div', class_='eKPi4')
    if heading:
        results_for_span = heading.find('span', class_='gm7Ysb')
        location_span = heading.find('span', class_='BBwThe')
        
        if results_for_span and location_span:
            output['title'] = f"{results_for_span.text.strip()} {location_span.text.strip()}"
    
    return output

def _parse_location_use_precise_location(cmpt):
    output = {"title": None, "text": None}
    
    # Extract the main heading
    heading = cmpt.find('div', class_='eKPi4')
    if heading:
        results_for_span = heading.find('span', class_='gm7Ysb')
        location_span = heading.find('span', class_='BBwThe')
        
        if results_for_span and location_span:
            output['title'] = f"{results_for_span.text.strip()} {location_span.text.strip()}"
    
    return output
