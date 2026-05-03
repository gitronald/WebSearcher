from ..component_types import Section, types_in_section
from .ads import parse_ads
from .available_on import parse_available_on
from .banner import parse_banner
from .discussions_and_forums import parse_discussions_and_forums
from .footer import Footer
from .general import parse_general_results
from .general_questions import parse_general_questions
from .images import parse_images
from .knowledge import parse_knowledge_panel
from .knowledge_rhs import parse_knowledge_rhs
from .latest_from import parse_latest_from
from .local_news import parse_local_news
from .local_results import parse_local_results
from .locations import parse_locations
from .map_results import parse_map_results
from .news_quotes import parse_news_quotes
from .notices import parse_notices
from .people_also_ask import parse_people_also_ask
from .perspectives import parse_perspectives
from .recent_posts import parse_recent_posts
from .scholarly_articles import parse_scholarly_articles
from .searches_related import parse_searches_related
from .shopping_ads import parse_shopping_ads
from .short_videos import parse_short_videos
from .top_image_carousel import parse_top_image_carousel
from .top_stories import parse_top_stories
from .twitter_cards import parse_twitter_cards
from .twitter_result import parse_twitter_result
from .videos import parse_videos
from .view_more_news import parse_view_more_news

# Single source of parser dispatch: type name -> parser function.
# Sections come from the component_types registry; labels come from each
# type's ``label`` field. The dispatch dicts and label dicts below are
# derived from this map joined against the registry.
PARSERS = {
    "ad": parse_ads,
    "available_on": parse_available_on,
    "banner": parse_banner,
    "discover_more": Footer.parse_discover_more,
    "discussions_and_forums": parse_discussions_and_forums,
    "general": parse_general_results,
    "general_questions": parse_general_questions,
    "images": parse_images,
    "img_cards": Footer.parse_image_cards,
    "knowledge": parse_knowledge_panel,
    "knowledge_rhs": parse_knowledge_rhs,
    "latest_from": parse_latest_from,
    "local_news": parse_local_news,
    "local_results": parse_local_results,
    "locations": parse_locations,
    "map_results": parse_map_results,
    "news_quotes": parse_news_quotes,
    "notice": parse_notices,
    "omitted_notice": Footer.parse_omitted_notice,
    "people_also_ask": parse_people_also_ask,
    "perspectives": parse_perspectives,
    "recent_posts": parse_recent_posts,
    "scholarly_articles": parse_scholarly_articles,
    "searches_related": parse_searches_related,
    "shopping_ads": parse_shopping_ads,
    "short_videos": parse_short_videos,
    "top_image_carousel": parse_top_image_carousel,
    "top_stories": parse_top_stories,
    "twitter_cards": parse_twitter_cards,
    "twitter_result": parse_twitter_result,
    "videos": parse_videos,
    "view_more_news": parse_view_more_news,
}


def _section_parser_dict(section: Section) -> dict:
    return {t.name: PARSERS[t.name] for t in types_in_section(section) if t.name in PARSERS}


def _section_parser_labels(section: Section) -> dict:
    return {t.name: t.label for t in types_in_section(section) if t.name in PARSERS}


header_parser_dict = _section_parser_dict("header")
main_parser_dict = _section_parser_dict("main")
footer_parser_dict = _section_parser_dict("footer")

header_parser_labels = _section_parser_labels("header")
main_parser_labels = _section_parser_labels("main")
footer_parser_labels = _section_parser_labels("footer")


def parse_unknown(cmpt) -> list:
    parsed_result = {
        "type": cmpt.type,
        "cmpt_rank": cmpt.cmpt_rank,
        "text": cmpt.elem.get_text("<|>", strip=True) if cmpt.elem else None,
    }
    return [parsed_result]


def parse_not_implemented(cmpt) -> list:
    """Placeholder function for component parsers that are not implemented"""
    parsed_result = {
        "type": cmpt.type,
        "cmpt_rank": cmpt.cmpt_rank,
        "text": cmpt.elem.get_text("<|>", strip=True),
        "error": "not implemented",
    }
    return [parsed_result]
