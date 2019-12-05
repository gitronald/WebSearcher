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
            cmpt_type = 'knowledge'
        elif cmpt.find('div', {'class':'knavi'}):
            cmpt_type = 'knowledge'
        elif cmpt.find('div', {'class':'kp-blk'}):
            if cmpt.find('g-tray-header'):
                h3 = cmpt.find('h3')
                if h3.text == 'Quotes in the news':
                    cmpt_type = 'news_quotes'
            elif cmpt.find('h2') and cmpt.find('h2').text == 'People also ask': 
                # <h2 class="MA9Une">People also ask</h2>
                cmpt_type = 'people_also_ask'
            else:
                cmpt_type = 'knowledge'

        elif cmpt.find('h2'):
            h2 = cmpt.find('h2')
            
            if h2.text == 'Featured snippet from the web': 
                # "<h2 class="bNg8Rb">Featured snippet from the web</h2>"
                cmpt_type = 'knowledge'
                
            if h2.text == 'Unit Converter':
                # <h2 class="bNg8Rb">Unit Converter</h2>
                cmpt_type = 'knowledge'

            if h2.text == 'Sports Results':
                # <h2 class="bNg8Rb">Sports Results</h2>
                cmpt_type = 'knowledge'

            elif h2.text == 'Web results': 
                # <h2 class="bNg8Rb">Web results</h2>
                cmpt_type = 'general' 

            elif h2.text == 'Resultados de la Web': 
                # <h2 class="bNg8Rb">Resultados de la Web</h2>
                cmpt_type = 'general' 

            elif h2.text == 'Web Result with Site Links': 
                # <h2 class="bNg8Rb">Web Result with Site Links</h2>
                cmpt_type = 'general' #_menu

            elif h2.text == 'Local Results': 
                # <h2 class="bNg8Rb">Local Results</h2> 
                cmpt_type = 'local_results' 

            elif h2.text == 'Map Results':
                # <h2 class="bNg8Rb">Map Results</h2>
                cmpt_type = 'map_results'

            elif h2.text == 'Twitter Results':
                if cmpt.find('g-section-with-header'):
                    cmpt_type = 'twitter_cards'
                else:
                    cmpt_type = 'twitter_result'

        elif cmpt.find('g-tray-header'):
            h3 = cmpt.find('h3')
            if h3.text == 'Quotes in the news':
                cmpt_type = 'news_quotes'

        elif cmpt.find('div', {'id':'imagebox_bigimages'}):
            cmpt_type = 'images'

        elif cmpt.find('g-section-with-header'):
            h3 = cmpt.find('h3')
            if h3:
                if h3.text.startswith('Top stories'): 
                    # Accounts for "Top stories for <query>"
                    cmpt_type = 'top_stories'
                elif h3.text.startswith('Videos'):  
                    # Accounts for "Videos for <query>"
                    cmpt_type = 'videos'
                elif h3.text.startswith('View more videos'):
                    cmpt_type = 'view_more_videos'
                elif h3.text.startswith('Latest from'):
                    # <h3 aria-level="2" role="heading">Latest from aol.com</h3>
                    cmpt_type = 'latest_from'
                elif h3.text.startswith('View more news'):
                    cmpt_type = 'view_more_news'
                elif h3.text.startswith('Images for'):
                    cmpt_type = 'images'


        elif '/Available on' in cmpt.text:
            cmpt_type = 'available_on'
        
        # General with people also ask style questions
        elif cmpt.find('div', {'class':'ifM9O'}):
            cmpt_type = 'general_questions'

        # Return type or unknown if null (not tagged by an existing classifier)
        return cmpt_type if cmpt_type else 'unknwon'
        
    except Exception:
        log.exception('Unknown Component')
        return 'unknown'
        