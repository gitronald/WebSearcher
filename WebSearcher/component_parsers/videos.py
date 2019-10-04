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

def parse_videos(cmpt):
    """Parse a videos component

    These components contain links to videos, frequently to YouTube.
    
    Args:
        cmpt (bs4 object): A videos component
    
    Returns:
        list : list of parsed subcomponent dictionaries
    """
    subs = cmpt.find_all('g-inner-card')
    return [parse_video(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def parse_video(sub, sub_rank=0):
    """Parse a videos subcomponent
    
    Args:
        sub (bs4 object): A video subcomponent
    
    Returns:
        dict : parsed subresult
    """
    parsed = {'type':'videos', 'sub_rank':sub_rank}
    parsed['url'] = sub.find('a')['href']
    parsed['title'] = sub.find('div', {'role':'heading'}).text

    text_div, citetime_div = sub.find_all('div',{'class':'MjS0Lc'})
    parsed['text'] = text_div.text if text_div else None

    if citetime_div:
        # Sometimes there is only a cite
        citetime = list(citetime_div.find('div',{'class':'zECGdd'}).children)
        if len(citetime) == 2:
            cite, timestamp = citetime       
            parsed['cite'] = cite.text
            parsed['timestamp'] = timestamp.replace(' - ', '')
        else:
            parsed['cite'] = citetime[0].text

    parsed['details'] = {} 
    parsed['details']['img_url'] = get_img_url(sub)
    return parsed

def get_img_url(soup):
    """Extract image source"""    
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']
