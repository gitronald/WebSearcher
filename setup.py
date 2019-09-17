# WebSearcher - Tools for conducting, collecting, and parsing web search
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

import setuptools
import pandas as pd

def get_readme_title(fp='README.md', delim='# ', stop_at=1):
    readme = pd.read_csv(fp, sep='\n', squeeze=True, header=None)
    selected = readme[readme.str.startswith(delim)].iloc[0].replace('# ', '')
    return selected

def get_readme_abstract(fp='README.md', delim='#', stop_at=1):
    readme = pd.read_csv(fp, sep='\n', squeeze=True, header=None)
    selected = readme[readme.str.startswith(delim)].index[:stop_at]
    start, stop = selected[0], selected[-1]
    abstract = selected[start:stop]
    return abstract.str.cat(sep=' ').strip() 

setuptools.setup(
    name='WebSearcher',
    version='version='0.1.2'',
    url='http://github.com/gitronald/WebSearcher',
    author='Ronald E. Robertson',
    author_email='rer@ccs.neu.edu',
    license='BSD-3-Clause',
    description=get_readme_title(),
    packages=setuptools.find_packages(),
    install_requires=['requests','lxml','bs4','brotli',
                      'tldextract','emoji','pandas'],
    zip_safe=False
)
