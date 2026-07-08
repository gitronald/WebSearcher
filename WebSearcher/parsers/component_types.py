"""Single source of truth for component type metadata.

Each :class:`ComponentType` describes a parsable result type:
- ``name``: canonical id used as the ``type`` field on parsed results
- ``label``: human-readable label (mirrors parser registry labels)
- ``sections``: SERP sections this type belongs to (``header``, ``main``, or ``footer``)
- ``header_texts``: per-heading-level header text → type matches used by
  :class:`WebSearcher.classifiers.main.ClassifyMainHeader`
- ``sub_types``: known sub_type values produced by the parser
- ``description``: short human-readable description

Consumers:
- :class:`WebSearcher.classifiers.main.ClassifyMainHeader` reads ``header_texts``
  via :func:`header_text_to_type`
- :mod:`WebSearcher.parsers.components` derives per-section parser dispatch dicts
  and labels via :func:`types_in_section` and :data:`TYPES_BY_NAME`
"""

from dataclasses import dataclass, field
from typing import Literal

Section = Literal["header", "main", "footer"]


@dataclass(frozen=True)
class ComponentType:
    name: str
    label: str
    sections: tuple[Section, ...] = ()
    header_texts: dict[int, tuple[str, ...]] = field(default_factory=dict)
    sub_types: tuple[str, ...] = ()
    description: str = ""


COMPONENT_TYPES: tuple[ComponentType, ...] = (
    # ----- Header section -----
    ComponentType(
        name="notice",
        label="Notices",
        sections=("header",),
        sub_types=(
            "query_edit",
            "query_edit_no_results",
            "query_suggestion",
            "location_choose_area",
            "location_use_precise_location",
            "language_tip",
        ),
        description="Special notices and suggestions shown at the top of search results",
    ),
    ComponentType(
        name="top_image_carousel",
        label="Top Image Carousel",
        sections=("header",),
        description="Carousel of images displayed at the top of search results",
    ),
    # ----- Main section -----
    ComponentType(
        name="ad",
        label="Ad",
        sections=("main",),
        sub_types=("standard", "legacy", "secondary", "submenu"),
        description="Advertisements displayed in search results",
    ),
    ComponentType(
        name="ai_overview",
        label="AI Overview",
        sections=("main",),
        sub_types=("flat", "sectioned"),
        description="AI-generated synthesized answer panel",
    ),
    ComponentType(
        name="available_on",
        label="Available On",
        sections=("main",),
        description="Where entertainment content is available to stream or purchase",
    ),
    ComponentType(
        name="banner",
        label="Banner",
        sections=("main",),
        description="Banner notifications shown at top of results",
    ),
    ComponentType(
        name="buying_guide",
        label="Buying Guide",
        sections=("main",),
        header_texts={2: ("Buying guide",)},
        description="Faceted buying-guide accordion (label -> question rows)",
    ),
    ComponentType(
        name="articles",
        label="Articles",
        sections=("main",),
        header_texts={2: ("Articles",)},
        description="Entity-panel articles module (external article links)",
    ),
    ComponentType(
        name="datasets",
        label="Datasets",
        sections=("main",),
        header_texts={2: ("Datasets",)},
        description="Dataset-search results module (title + source link per dataset)",
    ),
    ComponentType(
        name="directions",
        label="Directions",
        sections=("main",),
        header_texts={2: ("Directions", "Ubicaciones")},
    ),
    ComponentType(
        name="discussions_and_forums",
        label="Discussions & Forums",
        sections=("main",),
        header_texts={2: ("Discussions and forums", "Questions & answers")},
        description="Forum and discussion board results",
    ),
    ComponentType(
        name="election_dates",
        label="Election Dates",
        sections=("main",),
        # Renders at aria-level 2, or level 3 as an entity-panel submodule
        # ("Election dates - Primaries - Michigan").
        header_texts={2: ("Election dates",), 3: ("Election dates",)},
        description="Calendar of upcoming primary/general election dates",
    ),
    ComponentType(
        name="election_resources",
        label="Election Resources",
        sections=("main",),
        header_texts={2: ("Election resources",)},
        description="Official voter-resource panel (register, where/how to vote)",
    ),
    ComponentType(
        name="election_results",
        label="Election Results",
        sections=("main",),
        header_texts={2: ("Election results", "Presidential primary results")},
        description="Live election-results tracker / primary-results panel",
    ),
    ComponentType(
        name="general",
        label="General",
        sections=("main", "footer"),
        header_texts={
            2: (
                "Complementary Results",
                "Web Result with Site Links",
                "Web results",
                "Resultados de la Web",
                "AI-powered overview",
                "Visión general creada por IA",
            ),
        },
        sub_types=(
            "video",
            "submenu",
            "submenu_mini",
            "submenu_rating",
            "submenu_scholarly",
            "submenu_product",
            "subresult",
            "image_strip",
        ),
        description="Standard web search results",
    ),
    ComponentType(
        name="general_questions",
        label="General Questions",
        sections=("main",),
        description="General results with related questions",
    ),
    ComponentType(
        name="images",
        label="Images",
        sections=("main",),
        header_texts={
            2: ("Images", "Imágenes"),
            3: ("Images for",),
        },
        sub_types=("multimedia", "medium", "small"),
        description="Image search results",
    ),
    ComponentType(
        name="flights",
        label="Flights",
        sections=("main",),
    ),
    ComponentType(
        name="jobs",
        label="Jobs",
        sections=("main",),
        header_texts={2: ("Jobs", "Empleos")},
    ),
    ComponentType(
        name="knowledge",
        label="Knowledge",
        sections=("main",),
        header_texts={
            2: (
                "Things to know",
                "Cosas que debes saber",
                "Calculator Result",
                "Featured snippet from the web",
                "Fragmento destacado",
                "Finance Results",
                "Resumen de Mercado",
                "From sources across the web",
                "Knowledge Result",
                "Resultado de traducción",
                "Sports Results",
                "Table",
                "Posiciones",
                "Stat Leaders",
                "Líderes de estadísticas",
                "Teams",
                "Equipos",
                "Players",
                "Jugadores",
                "Translation Result",
                "Unit Converter",
                "Weather Result",
                "Clima",
                "Artworks",
                "Obras de arte",
                "Songs",
                "Canciones",
                "Albums",
                "Álbumes",
                "About",
                "Información",
                "Profiles",
                "Perfiles",
            ),
        },
        # NB: ``knowledge`` is an *open* sub_type space. Beyond the fixed values
        # below, ``parse_knowledge_panel``'s JNkvid branch mints a slug from the
        # section heading (e.g. ``movies``, ``songs``, ``lyrics``, ``played-by``,
        # ``cast-and-crew``). This tuple enumerates the closed set; the slug
        # values are intentionally not exhaustive. (The RHS column, registered
        # separately as ``knowledge_rhs``, emits its own ``type="side_bar"`` rows.)
        sub_types=(
            "featured_results",
            "featured_snippet",
            "unit_converter",
            "sports",
            "weather",
            "finance",
            "dictionary",
            "translate",
            "calculator",
            "election",
            "things_to_know",
            "panel",
        ),
        description="Knowledge panels and featured snippets",
    ),
    ComponentType(
        name="knowledge_rhs",
        label="Knowledge RHS",
        sections=("main",),
        # Component type assigned to the RHS column container; its parser emits
        # result rows as ``type="side_bar"`` with ``sub_type="panel"`` (the main
        # entity panel) or ``sub_type="links"`` (link boxes).
        description="Knowledge panels in right-hand sidebar",
    ),
    ComponentType(
        name="latest_from",
        label="Latest From",
        sections=("main",),
        header_texts={
            2: ("Latest from",),
            3: ("Latest from",),
        },
        description="Latest news results from specific sources",
    ),
    ComponentType(
        name="local_news",
        label="Local News",
        sections=("main",),
        header_texts={2: ("Local news", "Noticias Locales", "Latest in local")},
        description="News results specific to a location",
    ),
    ComponentType(
        name="local_results",
        label="Local Results",
        sections=("main",),
        header_texts={
            2: (
                "Local Results",
                "Locations",
                "Places",
                "Sitios",
                "Businesses",
                "locations",
            ),
        },
        # Closed category set mapped from the component header by phrase (see
        # local_results._LOCAL_RESULTS_CATEGORIES / _header_to_sub_type). Headers
        # that match no category leave sub_type None rather than slugifying free
        # display text into a per-query value.
        sub_types=(
            "results_for",
            "places",
            "locations",
            "businesses",
            "availability",
        ),
        description="Map-based local business results",
    ),
    ComponentType(
        name="locations",
        label="Locations",
        sections=("main",),
        sub_types=("hotels",),
    ),
    ComponentType(
        name="map_results",
        label="Map Results",
        sections=("main",),
        header_texts={2: ("Map Results", "Choice Hotels", "Hoteles", "Hotel")},
        description="Map-only results",
    ),
    ComponentType(
        name="most_read_articles",
        label="Most-read Articles",
        sections=("main",),
        # Header-text-only: this type has no unique structural CSS signal (its
        # cards share generic classes), so it is classified purely by the English
        # header "Most-read articles" via ClassifyMainHeader. A localized heading
        # is unclassifiable -- unlike buying_guide/products, it cannot be made
        # structural-first. Flagged; no fix planned.
        header_texts={2: ("Most-read articles",)},
        description="Editorial article carousel (one card per publisher)",
    ),
    ComponentType(
        name="news_quotes",
        label="News Quotes",
        sections=("main",),
        header_texts={3: ("Quotes in the news",)},
        description="Quote snippets from news articles",
    ),
    ComponentType(
        name="people_also_ask",
        label="People Also Ask",
        sections=("main", "footer"),
        header_texts={2: ("People also ask", "Más preguntas")},
        description="Related questions that people search for",
    ),
    ComponentType(
        name="perspectives",
        label="Perspectives & Opinions",
        sections=("main",),
        header_texts={
            2: (
                "Perspectives & opinions",
                "Perspectives",
                "What people are saying",
            ),
        },
        sub_types=(
            "perspectives",
            "perspectives_&_opinions",
            "what_people_are_saying",
        ),
        description="Opinion and perspective results",
    ),
    ComponentType(
        name="places_nearby",
        label="Places Nearby",
        sections=("main",),
        header_texts={2: ("Explore places nearby",)},
        description="Local places carousel (name per nearby place; JS-driven, no urls)",
    ),
    ComponentType(
        name="products",
        label="Products",
        sections=("main",),
        # The tray carousel ("Popular products" / "More products") renders its
        # title in an aria-level-2 g-tray-header span; the immersive grid uses an
        # aria-level-3 "Popular products" heading.
        header_texts={2: ("Popular products", "More products"), 3: ("Popular products",)},
        sub_types=("grid", "brands"),
        description="Organic shopping packs: popular-products grids and brand carousels",
    ),
    ComponentType(
        name="promo",
        label="Promo",
        sections=("main",),
        sub_types=("shopping",),
        description="Promotional banner (e.g. 'Save with deals / Shop deals' shopping CTA)",
    ),
    ComponentType(
        name="refine_by",
        label="Refine By",
        sections=("main",),
        # "Refine by brand"/"Refine by color" and the product-category variant
        # "Refine Wall Clocks"/"Refine Shure SM7B Microphones" -- both are the same
        # ULSxyf chip module, so the "Refine " prefix (trailing space) matches at L2.
        header_texts={2: ("Refine ",)},
        description="Faceted product-filter chips linking to a refined search",
    ),
    ComponentType(
        name="shopping_ideas",
        label="Shopping Ideas",
        sections=("main",),
        # "Related categories nearby" is the local-shopping variant (chips link to
        # "shop <category> near me"), rendered as a level-3 submodule heading.
        header_texts={2: ("Shopping ideas",), 3: ("Related categories nearby",)},
        description="Product-category idea chips linking to a category search",
    ),
    ComponentType(
        name="recent_posts",
        label="Recent Posts",
        sections=("main",),
        # The standalone main-column module ("Latest posts from <entity>",
        # ``lab/cluster/*`` attrids) renders its heading at aria-level 3; the
        # social-carousel variant heads "Posts from <entity>" at aria-level 2.
        header_texts={
            2: ("Recent posts", "Latest posts from", "Posts from"),
            3: ("Latest posts from",),
        },
    ),
    ComponentType(
        name="recipes",
        label="Recipes",
        sections=("main",),
        # The standalone main-column carousel renders its heading at aria-level 2
        # ("Popular recipes" / "More popular recipes" / bare "Recipes"), often
        # wrapped in an async-load "Preferences saved ... RETRY" state chrome that
        # leaves the heading intact; the inline "Recipes" variant is aria-level 3.
        header_texts={
            2: ("Popular recipes", "More popular recipes", "Recipes"),
            3: ("Recipes", "Recetas"),
        },
    ),
    ComponentType(
        name="scholarly_articles",
        label="Scholar Articles",
        sections=("main",),
        header_texts={3: ("Scholarly articles for", "Artículos académicos para")},
        description="Google Scholar results",
    ),
    ComponentType(
        name="searches_related",
        label="Related Searches",
        sections=("main", "footer"),
        header_texts={
            2: (
                "Additional searches",
                "More searches",
                "Ver más",
                "Other searches",
                "People also search for",
                "También se buscó",
                "Related",
                "Related searches",
                "Related to this search",
                "Searches related to",
                # Advertiser-flavored suggestion list ("These searches help you
                # find relevant offers from advertisers"); rows are plain
                # google.com/search?q= query links like the classic variants.
                "Find related products & services",
            ),
            3: ("Related searches",),
        },
        sub_types=(
            "additional_searches",
            "related_searches",
            "find_related_products_&_services",
        ),
        description="Related search terms",
    ),
    ComponentType(
        name="short_videos",
        label="Short Videos",
        sections=("main",),
    ),
    ComponentType(
        name="supercat_cluster",
        label="Supercat Cluster",
        sections=("main",),
        # No header_texts: classified structurally by its ``Supercat*ClusterTitle``
        # data-attrid (the label -- "What to read", "Courses", "Explore stocks" --
        # varies by content, but the attrid family is stable).
        description="JS-hydrated discovery cluster (recommended books/courses/stocks; title per item)",
    ),
    ComponentType(
        name="shopping_ads",
        label="Shopping Ad",
        sections=("main",),
        description="Product shopping advertisements",
    ),
    ComponentType(
        name="top_stories",
        label="Top Stories",
        sections=("main",),
        header_texts={
            2: (
                "Top stories",
                "Noticias Destacadas",
                "Noticias Principales",
                "News",
                "Noticias",
                "Market news",
                # Contextual news-article carousels (same g-section-with-header
                # card layout, parsed by parse_top_stories).
                "For context",
                "States in the news",
            ),
            3: ("Top stories", "Noticias destacadas", "Noticias Principales"),
        },
        description="Featured news stories",
    ),
    ComponentType(
        name="twitter",
        label="Twitter",
        sections=("main",),
        header_texts={2: ("Twitter Results",)},
        description="Transient label converted to twitter_cards or twitter_result",
    ),
    ComponentType(
        name="twitter_cards",
        label="Twitter Cards",
        sections=("main",),
        description="Twitter content displayed in cards",
    ),
    ComponentType(
        name="twitter_result",
        label="Twitter Result",
        sections=("main",),
        description="Individual Twitter result",
    ),
    ComponentType(
        name="videos",
        label="Videos",
        sections=("main",),
        header_texts={
            2: ("Videos",),
            3: ("Videos",),
        },
        description="Video results",
    ),
    ComponentType(
        name="view_more_news",
        label="View More News",
        sections=("main",),
        header_texts={3: ("View more news", "Más noticias")},
        description="News result expansion links",
    ),
    ComponentType(
        name="view_more_videos",
        label="View More Videos",
        sections=("main",),
        header_texts={3: ("View more videos", "Más videos", "Ver más")},
    ),
    # ----- Footer section -----
    ComponentType(
        name="discover_more",
        label="Discover More",
        sections=("footer",),
        description="'Discover more' suggestions",
    ),
    ComponentType(
        name="img_cards",
        label="Image Cards",
        sections=("footer",),
        description="Image cards displayed in footer",
    ),
    ComponentType(
        name="omitted_notice",
        label="Omitted Notice",
        sections=("footer",),
        header_texts={2: ("Notices about Filtered Results",)},
        description="Notices about filtered results",
    ),
    # ----- Special (no section) -----
    ComponentType(
        name="unknown",
        label="Unknown",
        description="Unclassified components",
    ),
    ComponentType(
        name="unclassified",
        label="Unclassified",
        description="Default type in the BaseResult model",
    ),
)


# Derived lookups built once at import time
TYPES_BY_NAME: dict[str, ComponentType] = {t.name: t for t in COMPONENT_TYPES}


_HEADER_TEXT_TO_TYPE: dict[int, dict[str, str]] = {
    level: {text: t.name for t in COMPONENT_TYPES for text in t.header_texts.get(level, ())}
    for level in {lvl for t in COMPONENT_TYPES for lvl in t.header_texts}
}


def header_text_to_type(level: int) -> dict[str, str]:
    """Inverted: ``{header text: type name}`` for a given heading level."""
    return _HEADER_TEXT_TO_TYPE.get(level, {})


def types_in_section(section: Section) -> tuple[ComponentType, ...]:
    """Types that can appear in the given section."""
    return tuple(t for t in COMPONENT_TYPES if section in t.sections)
