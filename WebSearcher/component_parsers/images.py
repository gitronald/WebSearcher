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

def parse_images(cmpt):
    """Parse an image component
    
    Args:
        cmpt (bs4 object): an image component
    
    Returns:
        list: list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('img')
    return [parse_img(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_img(sub, sub_rank=0):
    """Parse an image subcomponent
    
    Args:
        sub (bs4 object): an image subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'images', 'sub_rank':sub_rank}
    if 'title' in sub:
        parsed['img_url'] = sub['title'] # Hacky, 'src' is always the same though
    return parsed
