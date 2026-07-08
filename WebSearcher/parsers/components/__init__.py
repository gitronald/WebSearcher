"""Component parsers and the type-name → parser dispatch registry.

Parser contract
---------------
Every component parser is a module-level function (no parser classes). The
registry below (:data:`PARSERS`) maps a component type name to its entry
parser. ``Component.run_parser`` calls each entry parser with the component's
selectolax node, so:

- Entry parser signature: ``def parse_<type>(elem: Node) -> list[dict]``. The
  first parameter is always ``elem`` -- a selectolax ``LexborNode``, never the
  ``Component`` -- because ``Component.run_parser`` calls ``parser_func(self.elem)``
  with that single argument.
- Some parsers also accept an optional ``sub_rank: int = 0`` second parameter so
  they can be reused as sub-parsers (e.g. ``perspectives`` delegates to
  ``top_stories``); the dispatcher never passes it.
- ``parse_unknown`` is the catch-all for components classified as ``unknown``.
  Components with a known type but no registered parser are reported by the
  ``Component`` itself as a ``"not implemented"`` error -- there is no
  parser-side placeholder.
- Returns ``list[dict]``; each dict carries at least ``type``. Parsers that emit
  multiple sub-results set ``sub_rank`` to order them; otherwise ``BaseResult``
  defaults ``sub_rank`` to ``0``.
- Per-item helpers take a sub-node and are named ``sub``:
  ``def parse_<type>_item(sub: Node, sub_rank: int = 0) -> dict``.
- Module-level constants (selector tables, sub-type text maps) use
  ``UPPER_SNAKE_CASE`` and are built once at import.
"""

from ..._slx import get_text
from ..component_types import Section, types_in_section
from .ads import parse_ads
from .ai_overview import parse_ai_overview
from .available_on import parse_available_on
from .banner import parse_banner
from .buying_guide import parse_buying_guide
from .datasets import parse_datasets
from .discussions_and_forums import parse_discussions_and_forums
from .elections import parse_election_dates, parse_election_resources, parse_election_results
from .flights import parse_flights
from .footer import parse_discover_more, parse_img_cards, parse_omitted_notice
from .general import parse_general_results
from .general_questions import parse_general_questions
from .images import parse_images
from .jobs import parse_jobs
from .knowledge import parse_knowledge_panel
from .knowledge_rhs import parse_knowledge_rhs
from .latest_from import parse_latest_from
from .local_news import parse_local_news
from .local_results import parse_local_results
from .locations import parse_locations
from .map_results import parse_map_results
from .most_read_articles import parse_most_read_articles
from .news_quotes import parse_news_quotes
from .notices import parse_notices
from .people_also_ask import parse_people_also_ask
from .perspectives import parse_perspectives
from .products import parse_products
from .promo import parse_promo
from .recent_posts import parse_recent_posts
from .recipes import parse_recipes
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
    "ai_overview": parse_ai_overview,
    "available_on": parse_available_on,
    "banner": parse_banner,
    "buying_guide": parse_buying_guide,
    "datasets": parse_datasets,
    "discover_more": parse_discover_more,
    "discussions_and_forums": parse_discussions_and_forums,
    "election_dates": parse_election_dates,
    "election_resources": parse_election_resources,
    "election_results": parse_election_results,
    "flights": parse_flights,
    "general": parse_general_results,
    "general_questions": parse_general_questions,
    "images": parse_images,
    "img_cards": parse_img_cards,
    "jobs": parse_jobs,
    "knowledge": parse_knowledge_panel,
    "knowledge_rhs": parse_knowledge_rhs,
    "latest_from": parse_latest_from,
    "local_news": parse_local_news,
    "local_results": parse_local_results,
    "locations": parse_locations,
    "map_results": parse_map_results,
    "most_read_articles": parse_most_read_articles,
    "news_quotes": parse_news_quotes,
    "notice": parse_notices,
    "omitted_notice": parse_omitted_notice,
    "people_also_ask": parse_people_also_ask,
    "perspectives": parse_perspectives,
    "products": parse_products,
    "promo": parse_promo,
    "recent_posts": parse_recent_posts,
    "recipes": parse_recipes,
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


def parse_unknown(elem) -> list:
    """Catch-all for components classified as ``unknown``: capture text only."""
    return [{"type": "unknown", "text": get_text(elem, "<|>", strip=True)}]
