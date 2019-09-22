# Copyright (C) 2017-2019 Ronald E. Robertson <rer@ronalderobertson.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from . import logger
log = logger.Logger().start(__name__)

def classify_type(cmpt):
    """Component classifier
    
    Args:
        cmpt (bs4 object): A Search component
    
    Returns:
        str: A classification of the component type
    """
    try:
    
        if cmpt.find('div', {'class':'knowledge-panel'}):
            return 'knowledge'
        elif cmpt.find('div', {'class':'knavi'}):
            return 'knowledge'
        elif cmpt.find('div', {'class':'kp-blk'}):
            if cmpt.find('g-tray-header'):
                h3 = cmpt.find('h3')
                if h3.text == 'Quotes in the news':
                    return 'news_quotes'
            
            h2 = cmpt.find('h2')  
            if h2 and h2.text == 'People also ask': 
                # <h2 class="MA9Une">People also ask</h2>
                return 'people_also_ask'
            
            return 'knowledge'

        h2 = cmpt.find('h2')
        if h2:
            if h2.text == 'Featured snippet from the web': 
                # "<h2 class="bNg8Rb">Featured snippet from the web</h2>"
                return 'knowledge'
                
            if h2.text == 'Unit Converter':
                # <h2 class="bNg8Rb">Unit Converter</h2>
                return 'knowledge'

            if h2.text == 'Sports Results':
                # <h2 class="bNg8Rb">Sports Results</h2>
                return 'knowledge'

            elif h2.text == 'Web results': 
                # <h2 class="bNg8Rb">Web results</h2>
                return 'general' 

            elif h2.text == 'Resultados de la Web': 
                # <h2 class="bNg8Rb">Resultados de la Web</h2>
                return 'general' 

            elif h2.text == 'Web Result with Site Links': 
                # <h2 class="bNg8Rb">Web Result with Site Links</h2>
                return 'general' #_menu

            elif h2.text == 'Local Results': 
                # <h2 class="bNg8Rb">Local Results</h2> 
                return 'local_results' 

            elif h2.text == 'Map Results':
                # <h2 class="bNg8Rb">Map Results</h2>
                return 'map_results'

            elif h2.text == 'Twitter Results':
                if cmpt.find('g-section-with-header'):
                    return 'twitter_cards'
                else:
                    return 'twitter_result'

        elif cmpt.find('g-tray-header'):
            h3 = cmpt.find('h3')
            if h3.text == 'Quotes in the news':
                return 'news_quotes'

        elif cmpt.find('div', {'id':'imagebox_bigimages'}):
            return 'images'

        elif cmpt.find('g-section-with-header'):
            h3 = cmpt.find('h3')
            if h3:
                if h3.text.startswith('Top stories'): # Accounts for Top stories for <query>
                    return 'top_stories'
                elif h3.text.startswith('Videos'):  # Accounts for Videos for <query>
                    return 'videos'
                elif h3.text.startswith('View more videos'):
                    return 'view_more_videos'
                elif h3.text.startswith('Latest from'):
                    return 'latest_from'
                elif h3.text.startswith('View more news'):
                    return 'view_more_news'
                    # <h3 aria-level="2" role="heading">Latest from aol.com</h3>

        elif '/Available on' in cmpt.text:
            return 'available_on'

    except Exception:
        log.exception('Unknown Component')
        return 'unknown'
        