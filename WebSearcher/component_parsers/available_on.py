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

def parse_available_on(cmpt, sub_rank=0):
    """Parse an available component

    These components contain a carousel of thumbnail images with links to
    entertainment relevant to query 
    
    Args:
        cmpt (bs4 object): An available on component
    
    Returns:
        dict : parsed component
    """
    parsed = {'type':'available_on', 'sub_rank':sub_rank}

    parsed['title'] = cmpt.find('span', {'class':'GzssTd'}).text

    details = []
    options = cmpt.find_all('div', {'class':'kno-fb-ctx'})
    for o in options:
        option = {}
        option['title'] = o.find('div', {'class':'i3LlFf'}).text
        option['cost']  = o.find('div', {'class':'V8xno'}).text
        option['url']   = o.find('a')['href']
        details.append(option)
    parsed['details'] = details
    return [parsed]
