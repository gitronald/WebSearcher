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

def parse_scholarly_articles(cmpt):
    """Parse a scholarly articles component

    These components contain links to academic articles via Google Scholar
    
    Args:
        cmpt (bs4 object): A scholarly_articles component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    data_list = []
    subs = cmpt.find_all('tr')[1].find_all('div')
    return [parse_article(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_article(sub, sub_rank=0):
    """Parse a scholarly articles subcomponent
    
    Args:
        sub (bs4 object): A scholarly articles subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'scholarly_articles', 'sub_rank':sub_rank}
    parsed['title'] = sub.text
    if sub.find('a'):
        parsed['url'] = sub.find('a').attrs['href']
        parsed['title'] = sub.find('a').text
        parsed['cite'] = sub.find('span').text.replace(' - \u200e', '')
    return parsed
