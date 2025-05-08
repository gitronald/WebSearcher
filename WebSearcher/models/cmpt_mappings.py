"""
Metadata about WebSearcher result types and subtypes.
This provides documentation and structure for the various result types parsed by WebSearcher.
"""

# Header result types with descriptions and subtypes
HEADER_RESULT_TYPES = {
    "notice": {
        "description": "Special notices and suggestions shown at the top of search results",
        "sub_types": [
            "query_edit",
            "query_edit_no_results",
            "query_suggestion",
            "location_choose_area",
            "location_use_precise_location",
            "language_tip",
        ],
    },
    "top_image_carousel": {
        "description": "Carousel of images displayed at the top of search results",
        "sub_types": [],
    },
}

# Main result types with descriptions and subtypes
MAIN_RESULT_TYPES = {
    "ad": {
        "description": "Advertisements displayed in search results",
        "sub_types": ["standard", "legacy", "secondary", "submenu"],
    },
    "available_on": {
        "description": "Where entertainment content is available to stream or purchase",
        "sub_types": [],
    },
    "banner": {
        "description": "Banner notifications shown at top of results",
        "sub_types": [],
    },
    "discussions_and_forums": {
        "description": "Forum and discussion board results",
        "sub_types": [],
    },
    "general": {
        "description": "Standard web search results",
        "sub_types": [
            "video",
            "submenu",
            "submenu_mini",
            "submenu_rating",
            "submenu_scholarly",
            "submenu_product",
            "subresult",
        ],
    },
    "general_questions": {
        "description": "General results with related questions",
        "sub_types": [],
    },
    "images": {
        "description": "Image search results",
        "sub_types": ["multimedia", "medium", "small"],
    },
    "knowledge": {
        "description": "Knowledge panels and featured snippets",
        "sub_types": [
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
            "panel",
        ],
    },
    "latest_from": {
        "description": "Latest news results from specific sources",
        "sub_types": [],
    },
    "local_news": {
        "description": "News results specific to a location",
        "sub_types": [],
    },
    "local_results": {
        "description": "Map-based local business results",
        "sub_types": ["places", "locations", "businesses"],  # Dynamically generated
    },
    "map_results": {"description": "Map-only results", "sub_types": []},
    "news_quotes": {
        "description": "Quote snippets from news articles",
        "sub_types": [],
    },
    "notice": {
        "description": "Special notices about searches",
        "sub_types": [
            "query_edit",
            "query_edit_no_results",
            "query_suggestion",
            "location_choose_area",
            "location_use_precise_location",
            "language_tip",
        ],
    },
    "people_also_ask": {
        "description": "Related questions that people search for",
        "sub_types": [],
    },
    "perspectives": {"description": "Opinion and perspective results", "sub_types": []},
    "scholarly_articles": {"description": "Google Scholar results", "sub_types": []},
    "searches_related": {
        "description": "Related search terms",
        "sub_types": [
            "additional_searches",
            "related_searches",
        ],  # Dynamically generated
    },
    "shopping_ads": {"description": "Product shopping advertisements", "sub_types": []},
    "top_image_carousel": {
        "description": "Carousel of images displayed at top of page",
        "sub_types": [],
    },
    "top_stories": {"description": "Featured news stories", "sub_types": []},
    "twitter_cards": {
        "description": "Twitter content displayed in cards",
        "sub_types": [],
    },
    "twitter_result": {"description": "Individual Twitter result", "sub_types": []},
    "videos": {"description": "Video results", "sub_types": []},
    "view_more_news": {"description": "News result expansion links", "sub_types": []},
    "knowledge_rhs": {
        "description": "Knowledge panels in right-hand sidebar",
        "sub_types": [],
    },
    "unknown": {"description": "Unclassified components", "sub_types": []},
}

# Footer result types with descriptions and subtypes
FOOTER_RESULT_TYPES = {
    "img_cards": {"description": "Image cards displayed in footer", "sub_types": []},
    "searches_related": {
        "description": "Related searches displayed in footer",
        "sub_types": [
            "additional_searches",
            "related_searches",
        ],  # Dynamically generated
    },
    "discover_more": {"description": "'Discover more' suggestions", "sub_types": []},
    "general": {
        "description": "General results in footer",
        "sub_types": [
            "video",
            "submenu",
            "submenu_mini",
            "submenu_rating",
            "submenu_scholarly",
            "submenu_product",
            "subresult",
        ],
    },
    "people_also_ask": {"description": "Related questions in footer", "sub_types": []},
    "omitted_notice": {
        "description": "Notices about filtered results",
        "sub_types": [],
    },
}

# Special types not directly linked to parsers
SPECIAL_RESULT_TYPES = {
    "unclassified": {
        "description": "Default type in the BaseResult model",
        "sub_types": [],
    },
}

# Combined dictionary of all result types
ALL_RESULT_TYPES = {
    **HEADER_RESULT_TYPES,
    **MAIN_RESULT_TYPES,
    **FOOTER_RESULT_TYPES,
    **SPECIAL_RESULT_TYPES,
}
