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

def parse_twitter_result(cmpt, sub_rank=0):
    """Parse a Twitter single result component

    These components look like general components, but link to a Twitter account
    and sometimes have a tweet in the summary.
    
    Args:
        cmpt (bs4 object): A twitter cards component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """    
    parsed = {'type':'twitter_result', 'sub_rank':sub_rank}

    # Header
    header = cmpt.find('div', {'class':'DOqJne'})
    if header:
        title = header.find('g-link')
        # Get title
        if title:
            parsed['title'] = title.find('a').text
            parsed['url'] = title.find('a')['href']

        # Get citation
        cite = header.find('cite')
        if cite:
            parsed['cite'] = cite.text
    
    # Get snippet text, timestamp, and tweet url
    body, timestamp_url = cmpt.find('div', {'class':'tw-res'}).children
    parsed['text'] = body.text
    parsed['timestamp'] = timestamp_url.find('span').text
    parsed['details'] = timestamp_url.find('a')['href']
    return [parsed]