from .. import webutils

TITLE_SELECTORS = [
    ("div", {"class": "aiAXrc"}),
]


def parse_map_results(cmpt, sub_rank=0) -> list:
    """Parse a "Map Results" component

    These components contain an embedded map that is not followed by
    map results.

    Args:
        cmpt (bs4 object): A map results component

    Returns:
        dict : parsed result
    """
    return [
        {
            "type": "map_results",
            "sub_rank": sub_rank,
            "title": webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS),
        }
    ]
