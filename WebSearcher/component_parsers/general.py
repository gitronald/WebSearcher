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

def parse_general_results(cmpt):
    """Parse a general component

    The ubiquitous blue title, green citation, and black text summary results.
    Sometimes grouped into components of multiple general results. The
    subcomponent general results tend to have a similar theme.
    
    Args:
        cmpt (bs4 object): A general component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """

    subs = cmpt.find_all('div', {'class':'g'})
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_general_result(sub, sub_rank=0):
    """Parse a general subcomponent
    
    Args:
        sub (bs4 object): A general subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'general', 'sub_rank':sub_rank}

    # Get title
    # title_div = sub.find('h3').find('a')
    title_div = sub.find('div', {'class':'rc'})
    if title_div:
        parsed['title'] = title_div.find('h3').text
        parsed['url'] = title_div.find('a')['href']

    # Get citation
    cite = sub.find('cite')
    parsed['cite'] = cite.text if cite else None

    # Get snippet text
    body = sub.find('span', {'class':'st'})
    if body:
        if ' - ' in body.text[:20]:
            split_body = body.text.split(' - ')
            timestamp = split_body[0]
            parsed['text'] = ' - '.join(split_body[1:])
            parsed['timestamp'] = timestamp
        else:
            parsed['text'] = body.text
            parsed['timestamp'] = None
    if sub.find('div', {'class':'P1usbc'}): # Submenu
        parsed['type'] = 'general_submenu'
        parsed['details'] = parse_general_extra(sub)
    return parsed

def parse_general_extra(sub):
    """Parse submenu that appears below some general components"""
    item_list = list(sub.find('div', {'class':'P1usbc'}).children)
    return '|'.join([i.text for i in item_list])