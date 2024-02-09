# WebSearcher - Tools for conducting, collecting, and parsing web search
import setuptools
import codecs
import os

def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")

def get_readme_descriptions(fp='README.md', s='#', stop_at=2):
    with open(fp, 'r') as infile:
        # Extract short description (title) and long description
        descriptions = {'short': '', 'long': ''}
        readme = [l.strip() for l in infile.read().split('\n')]
        descriptions['short'] = readme[0].replace('# ', '')
        heading_idx = [idx for idx, l in enumerate(readme) if l.startswith(s)]
        descriptions['long'] = '  \n'.join(readme[:heading_idx[stop_at]])
    return descriptions

version = get_version("WebSearcher/__init__.py")
descriptions = get_readme_descriptions()

setuptools.setup(
    name='WebSearcher',
    version=version,
    url='http://github.com/gitronald/WebSearcher',
    author='Ronald E. Robertson',
    author_email='rer@acm.org',
    license='BSD-3-Clause',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License'
    ],
    description=descriptions['short'],
    long_description=descriptions['long'],
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    install_requires=[
        'requests',
        'lxml',
        'beautifulsoup4',
        'tldextract',
        'brotli',
        'pydantic'
    ],
    python_requires='>=3.6'
)
