"""Single source of truth for component type metadata.

Each :class:`ComponentType` describes a parsable result type:
- ``name``: canonical id used as the ``type`` field on parsed results
- ``label``: human-readable label (mirrors parser registry labels)
- ``sections``: SERP sections this type belongs to (``header``, ``main``, or ``footer``)
- ``header_texts``: per-heading-level header text → type matches used by
  :class:`WebSearcher.classifiers.header_text.ClassifyHeaderText`
- ``sub_types``: known sub_type values produced by the parser
- ``description``: short human-readable description

Consumers:
- :mod:`WebSearcher.classifiers.header_text` reads ``header_texts`` via
  :func:`header_text_to_type`
- :mod:`WebSearcher.component_parsers` derives per-section parser dispatch dicts
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
        sub_types=(
            "ai_overview",
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
        sub_types=("places", "locations", "businesses"),
        description="Map-based local business results",
    ),
    ComponentType(
        name="locations",
        label="Locations",
        sections=("main",),
    ),
    ComponentType(
        name="map_results",
        label="Map Results",
        sections=("main",),
        header_texts={2: ("Map Results", "Choice Hotels", "Hoteles", "Hotel")},
        description="Map-only results",
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
        name="products",
        label="Products",
        sections=("main",),
        header_texts={3: ("Popular products",)},
    ),
    ComponentType(
        name="recent_posts",
        label="Recent Posts",
        sections=("main",),
        header_texts={2: ("Recent posts", "Latest posts from")},
    ),
    ComponentType(
        name="recipes",
        label="Recipes",
        sections=("main",),
        header_texts={3: ("Recipes", "Recetas")},
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
            ),
            3: ("Related searches",),
        },
        sub_types=("additional_searches", "related_searches"),
        description="Related search terms",
    ),
    ComponentType(
        name="short_videos",
        label="Short Videos",
        sections=("main",),
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
        header_texts={3: ("View more news", "Más noticias", "Ver más")},
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


def header_text_to_type(level: int) -> dict[str, str]:
    """Inverted: ``{header text: type name}`` for a given heading level."""
    return {text: t.name for t in COMPONENT_TYPES for text in t.header_texts.get(level, ())}


def types_in_section(section: Section) -> tuple[ComponentType, ...]:
    """Types that can appear in the given section."""
    return tuple(t for t in COMPONENT_TYPES if section in t.sections)
