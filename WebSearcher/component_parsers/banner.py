from pydantic import BaseModel

class BannerResult(BaseModel):
    type: str = 'banner'
    sub_rank: int = 0
    sub_type: str = ''
    title: str = ''
    url: str = ''
    text: str = ''

def parse_banner(cmpt):
    """Parse a search suggestion component

    Args:
        cmpt (bs4 object): A search suggestion component
    
    Returns:
        list: List of BannerResult objects, with the main component and its subcomponents
    """
    banner_results = []

    # Header subcomponent
    banner_result_header = BannerResult(
        sub_type='header',
        title=get_result_text(cmpt, '.v3jTId'),
        text=get_result_text(cmpt, '.Cy9gW'),
    )
    banner_results.append(banner_result_header)

    # Suggestion subcomponents
    for i, suggestion in enumerate(cmpt.select('.TjBpC')):
        banner_result_suggestion = BannerResult(
            sub_rank=i + 1,
            sub_type='suggestion',
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


# ------------------------------------------------------------------------------

# with open("examples/banner-topicality.html", "r") as f:
#     html = f.read()

# wraprint(html, width=150)
# # print(ws.make_soup(html).prettify())

# l = parse_banner(ws.make_soup(html))
# df = pd.DataFrame([i.model_dump() for i in l])
# df