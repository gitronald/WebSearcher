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

def parse_ads(cmpt):
    """Parse ads from ad component

    Receives tuple (visible, ad_soup)

    """
    # visible_cue = cmpt.find('div', {'style':'padding:0 20px'})
    # visible = True if visible_cue else False
    
    # Find first style in center col, split into lines, find cue
    # visible, cmpt = cmpt
    
    subs = cmpt.find_all('li', {'class':'ads-ad'})
    # return [parse_ad(sub, sub_rank, visible) for sub_rank, sub in enumerate(subs)]
    return [parse_ad(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_ad(sub, sub_rank=0, visible=None):
    """Parse details of a single ad subcomponent, similar to general"""
    # parsed = {'type':'ad', 'sub_rank':sub_rank, 'visible':visible}
    parsed = {'type':'ad', 'sub_rank':sub_rank}

    header = sub.find('div', {'class':'ad_cclk'})
    parsed['title'] = header.find('h3').text
    parsed['url'] = header.find('cite').text
    parsed['text'] = sub.find('div', {'class':'ads-creative'}).text
    
    bottom_links = sub.find('ul')
    if bottom_links:
        parsed['details'] = [li.text for li in bottom_links.find_all('li')]

    return parsed
