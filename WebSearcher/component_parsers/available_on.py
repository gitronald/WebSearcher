from ..models.data import DetailsItem, DetailsList


def parse_available_on(cmpt, sub_rank=0) -> list:
    """Parse an available component

    These components contain a carousel of thumbnail images with links to
    entertainment relevant to query

    Args:
        cmpt (bs4 object): An available on component

    Returns:
        dict : parsed component
    """
    parsed = {"type": "available_on", "sub_rank": sub_rank}

    parsed["title"] = cmpt.find("span", {"class": "GzssTd"}).text

    details = DetailsList()
    for o in cmpt.find_all("div", {"class": "kno-fb-ctx"}):
        details.append(parse_available_on_item(o))
    parsed["details"] = details.to_dicts()
    return [parsed]


def parse_available_on_item(sub) -> DetailsItem:
    """Parse an available on item

    Args:
        sub (bs4 object): An available on option element

    Returns:
        DetailsItem : parsed item with title, url, and cost in misc
    """
    return DetailsItem(
        title=sub.find("div", {"class": "i3LlFf"}).text,
        url=sub.find("a")["href"],
        misc={"cost": sub.find("div", {"class": "V8xno"}).text},
    )
