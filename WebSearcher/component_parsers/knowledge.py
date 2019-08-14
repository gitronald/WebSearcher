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

def parse_knowledge_panel(cmpt, sub_rank=0):
    """Parse the Knowledge Box
    
    Args:
        cmpt (bs4 object): a knowledge component
    
    Returns:
        list: Return parsed dictionary in a list
    """
    parsed = {'type':'knowledge', 'sub_rank':sub_rank}

    # Get embedded result if it exists
    result = cmpt.find('div', {'class':'rc'})
    if result:
        parsed['title'] = result.find('h3').text
        parsed['url'] = result.find('a')['href']
        parsed['cite'] = result.find('cite').text

    # Get details
    details = {}

    heading = cmpt.find('div', {'role':'heading'})
    details['heading'] = heading.text if heading else None

    # Get all text
    if cmpt.find('h2') and cmpt.find('h2').text == 'Featured snippet from the web':
        details['subtype'] = 'featured_snippet'
        text = cmpt.find_all(['span'])
        details['text'] = '|'.join([s.text for s in text if s.text]) if text else None

    if cmpt.find('h2') and cmpt.find('h2').text == 'Unit Converter':
        details['subtype'] = 'unit_converter'
        text = cmpt.find_all(['span'])
        details['text'] = '|'.join([s.text for s in text if s.text]) if text else None

    if cmpt.find('h2') and cmpt.find('h2').text == 'Sports Results':
        details['subtype'] = 'sports'
        div = cmpt.find('div', {'class':'SwsxUd'})
        details['text'] = div.text if div else None

    else:
        details['subtype'] = 'panel'
        text = cmpt.find_all(['span','div','a'], text=True)
        details['text'] = '|'.join([t.text for t in text]) if text else None

    # Get image
    img_div = cmpt.find('div', {'class':'img-brk'})
    details['img_url'] = img_div.find('a')['href'] if img_div else None
    parsed['details'] = details

    return [parsed]
