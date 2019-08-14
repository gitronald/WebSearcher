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
from . import parse_top_stories

def parse_latest_from(cmpt):
    """Parse a "Latest news" component

    These components are the same as Top Stories, but have a different heading.
    
    Args:
        cmpt (bs4 object): A latest from component
    
    Returns:
        dict : parsed result
    """
    return parse_top_stories(cmpt, ctype='latest_from')