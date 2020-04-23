import pandas as pd
from .ads import parse_ads
from .knowledge import parse_knowledge_panel
from .general import parse_general_results
from .top_stories import parse_top_stories
from .latest_from import parse_latest_from
from .view_more_news import parse_view_more_news
from .news_quotes import parse_news_quotes
from .people_also_ask import parse_people_also_ask
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

# Component details dataframe
columns = ['type', 'func', 'label']
components = pd.DataFrame([
    ('ad', parse_ads, 'Ad'),
    ('knowledge', parse_knowledge_panel, 'Knowledge'),
    ('general', parse_general_results, 'General'),
    ('general_questions', parse_general_questions, 'General Questions'),
    ('general_menu', parse_general_results, 'General Submenu'),
    ('available_on', parse_available_on, 'Available On'),
    ('top_stories', parse_top_stories, 'Top Stories'), 
    ('latest_from', parse_latest_from, 'Latest From'),
    ('view_more_news', parse_view_more_news, 'View More News'),
    ('news_quotes', parse_news_quotes, 'News Quotes'),
    ('people_also_ask', parse_people_also_ask, 'People Also Ask'),
    ('local_results', parse_local_results, 'Local Results'),
    ('map_results', parse_map_results, 'Map Results'),
    ('images', parse_images, 'Images'),
    ('videos', parse_videos, 'Videos'),
    ('view_more_videos', parse_videos, 'View More Videos'),
    ('twitter_cards', parse_twitter_cards, 'Twitter Cards'),
    ('twitter_result', parse_twitter_result, 'Twitter Result'),
    ('scholarly_articles', parse_scholarly_articles, 'Scholar Articles'),
    ('footer', parse_footer, 'Footer')
], columns=columns)

# dict[type] = function
type_functions = components.set_index('type')['func'].to_dict()

# dict[type] = label
type_labels = components.set_index('type')['label'].to_dict()
