from .ads import parse_ads
from .knowledge import parse_knowledge_panel
from .general import parse_general_results
from .top_stories import parse_top_stories
from .latest_from import parse_latest_from
from .view_more_news import parse_view_more_news
from .news_quotes import parse_news_quotes
from .people_also_ask import parse_people_also_ask
from .searches_related import parse_searches_related
from .local_results import parse_local_results
from .map_results import parse_map_results
from .images import parse_images
from .videos import parse_videos
from .scholarly_articles import parse_scholarly_articles
from .twitter_cards import parse_twitter_cards
from .twitter_result import parse_twitter_result
from .general_questions import parse_general_questions
from .available_on import parse_available_on
from .footer import parse_footer
from .top_image_carousel import parse_top_image_carousel
from .knowledge_rhs import parse_knowledge_rhs
from .shopping_ads import parse_shopping_ads
from .perspectives import parse_perspectives
from .local_news import parse_local_news
from .banner import parse_banner

# Component details dataframe
columns = ['type', 'func', 'label']
components = [
    ('banner', parse_banner, 'Banner'),
    ('ad', parse_ads, 'Ad'),
    ('knowledge', parse_knowledge_panel, 'Knowledge'),
    ('general', parse_general_results, 'General'),
    ('general_questions', parse_general_questions, 'General Questions'),
    ('general_menu', parse_general_results, 'General Submenu'),
    ('general_subresult', parse_general_results, 'General Subresult'),
    ('available_on', parse_available_on, 'Available On'),
    ('top_stories', parse_top_stories, 'Top Stories'),
    ('local_news', parse_local_news, 'Local News'),
    ('latest_from', parse_latest_from, 'Latest From'),
    ('view_more_news', parse_view_more_news, 'View More News'),
    ('news_quotes', parse_news_quotes, 'News Quotes'),
    ('people_also_ask', parse_people_also_ask, 'People Also Ask'),
    ('local_results', parse_local_results, 'Local Results'),
    ('map_results', parse_map_results, 'Map Results'),
    ('perspectives', parse_perspectives, 'Perspectives & Opinions'),
    ('images', parse_images, 'Images'),
    ('videos', parse_videos, 'Videos'),
    ('view_more_videos', parse_videos, 'View More Videos'),
    ('twitter_cards', parse_twitter_cards, 'Twitter Cards'),
    ('twitter_result', parse_twitter_result, 'Twitter Result'),
    ('scholarly_articles', parse_scholarly_articles, 'Scholar Articles'),
    ('searches_related', parse_searches_related, 'Related Searches'),
    ('footer', parse_footer, 'Footer'),
    ('top_image_carousel', parse_top_image_carousel, 'Top Image Carousel'),
    ('knowledge_rhs', parse_knowledge_rhs, 'Knowledge RHS'),
    ('shopping_ad', parse_shopping_ads, 'Shopping Ad'),
    ('directions', parse_local_results, 'Directions'),
]

# Format {type: function}
type_functions = {i[0]:i[1] for i in components}

# Format {type: label}
type_labels = {i[0]:i[2] for i in components}
