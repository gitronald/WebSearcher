from ..models import BaseResult


def parse_banner(cmpt):
    """Parse a warning banner component

    Args:
        cmpt (bs4 object): A search suggestion component
    
    Returns:
        list: List of BannerResult objects, with the main component and its subcomponents
    """
    banner_results = []

    # Header subcomponent
    banner_result_header = BaseResult(
        type='banner',
        sub_type='header',
        sub_rank=0,
        title=get_result_text(cmpt, '.v3jTId'),
        text=get_result_text(cmpt, '.Cy9gW'),
    )
    banner_results.append(banner_result_header)

    # Suggestion subcomponents
    for i, suggestion in enumerate(cmpt.select('.TjBpC')):
        banner_result_suggestion = BaseResult(
            type='banner',
            sub_type='suggestion',
            sub_rank=i + 1,
            title=get_result_text(suggestion, '.AbPV3'),
            url=suggestion.get('href')
        )
        banner_results.append(banner_result_suggestion)

    return [banner.model_dump() for banner in banner_results]

def get_result_text(cmpt, selector):
    if cmpt.select_one(selector):
        return cmpt.select_one(selector).get_text(strip=True)
    else:
        return ""
