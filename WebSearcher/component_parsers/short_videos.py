from .. import webutils


def parse_short_videos(cmpt) -> list:
    """Parse a short videos carousel component

    Args:
        cmpt (bs4 object): A short videos carousel component

    Returns:
        list: list of parsed subcomponent dictionaries
    """
    # Filter to full card links (with heading), skip thumbnail-only duplicates
    cards = [
        a for a in cmpt.find_all("a", {"class": "rIRoqf"}) if a.find("div", {"role": "heading"})
    ]
    if not cards:
        return [{"type": "short_videos", "sub_rank": 0}]

    parsed_list = []
    for i, card in enumerate(cards):
        parsed = {
            "type": "short_videos",
            "sub_rank": i,
            "url": card.get("href"),
            "title": webutils.get_text(card, "div", {"role": "heading"}),
        }

        # Get source (YouTube, TikTok, etc.) and duration
        cite = webutils.get_text(card, "span", {"class": "xFMKFe"})
        if cite:
            parsed["cite"] = cite

        parsed_list.append(parsed)

    return parsed_list
