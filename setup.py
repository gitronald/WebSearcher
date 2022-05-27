# WebSearcher - Tools for conducting, collecting, and parsing web search
import setuptools

def get_readme_descriptions(fp='README.md', s='#', stop_at=2):
    with open(fp, 'r') as infile:
        # Extract description (title) and long description including n sections
        readme = [l.strip() for l in infile.read().split('\n')]
        description = readme[0].replace('# ', '')
        heading_idx = [idx for idx, l in enumerate(readme) if l.startswith(s)]
        long_description = '  \n'.join(readme[:heading_idx[stop_at]])
    return description, long_description
    
description, long_description = get_readme_descriptions()

setuptools.setup(
    name='WebSearcher',
    version='0.2.14',
    url='http://github.com/gitronald/WebSearcher',
    author='Ronald E. Robertson',
    author_email='rer@ccs.neu.edu',
    license='BSD-3-Clause',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License'
    ],
    description=description,
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    install_requires=['requests','lxml','bs4','tldextract','brotli'],
    python_requires='>=3.6'
)
