def parse_banner(cmpt) -> list:
    """Parse a warning banner component

    Args:
        cmpt (bs4 object): A search suggestion component
    
    Returns:
        list: List of BannerResult objects, with the main component and its subcomponents
    """
    parsed_list = []

    # Header subcomponent
    banner_result_header = {
        'type': 'banner',
        'sub_type': 'header',
        'sub_rank': 0,
        'title': _get_result_text(cmpt, '.v3jTId'),
        'text': _get_result_text(cmpt, '.Cy9gW'),
    }
    parsed_list.append(banner_result_header)

    # Suggestion subcomponents
    for i, suggestion in enumerate(cmpt.select('.TjBpC')):
        banner_result_suggestion = {
            'type': 'banner',
            'sub_type': 'suggestion',
            'sub_rank': i + 1,
            'title': _get_result_text(suggestion, '.AbPV3'),
            'url': suggestion.get('href')
        }
        parsed_list.append(banner_result_suggestion)

    return parsed_list

def _get_result_text(cmpt, selector) -> str:
    if cmpt.select_one(selector):
        return cmpt.select_one(selector).get_text(strip=True)
    else:
        return ""
