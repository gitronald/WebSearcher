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

def parse_map_results(cmpt, sub_rank=0):
    """Parse a "Map Results" component

    These components contain an embedded map that is not followed by 
    map results.
    
    Args:
        cmpt (bs4 object): A map results component
    
    Returns:
        dict : parsed result
    """
    parsed = {'type':'map_results', 'sub_rank':sub_rank}
    details = {}

    title_div = cmpt.find('div', {'class':'desktop-title-content'})
    details['title'] = title_div.text if title_div else None

    subtitle_span = cmpt.find('span', {'class':'desktop-title-subcontent'})
    details['subtitle'] = subtitle_span.text if subtitle_span else None

    img = cmpt.find('img', {'id':'lu_map'})
    details['img_title'] = img.attrs['title'] if 'title' in img.attrs else None
    parsed['details'] = details
    return [parsed]