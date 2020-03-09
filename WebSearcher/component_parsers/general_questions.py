# Copyright (C) 2017-2020 Ronald E. Robertson <rer@ronalderobertson.com>
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
from . import parse_general_results
from . import parse_people_also_ask

def parse_general_questions(cmpt):
    """Parse a General + People Also Ask hybrid component

    These components consist of a general result followed by a people also
    ask component with 3 subresults (questions).
    
    Args:
        cmpt (bs4 object): A latest from component
    
    Returns:
        dict : parsed result
    """

    result = parse_general_results(cmpt)
    questions = parse_people_also_ask(cmpt)
    result[0]['details'] = questions[0]['details']
    result[0]['type'] = 'general_questions'
    return result


