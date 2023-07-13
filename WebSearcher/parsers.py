from . import webutils
from .component_classifier import classify_type
from .component_parsers import type_functions
from .component_parsers.footer import extract_footer, extract_footer_components
from . import logger
log = logger.Logger().start(__name__)

import traceback
from bs4 import BeautifulSoup

UNKNOWN_COMPONENT = {
    'sub_rank':0, 
    'type': 'unknown'
}

def parse_query(soup):
    """Parse query from title of html soup"""
    title = str(soup.html.find('title'))
    return webutils.strip_html_tags(title).split(" - ")[0]

def parse_lang(soup):
    """Parse language from html tags"""
    try:
        return soup.find('html').attrs['lang']
    except Exception as e:
        log.exception('Error while parsing language')
        return None

def get_component_parser(cmpt_type, cmpt_funcs=type_functions):
    """Returns the parser for a given component type"""
    try:
        return cmpt_funcs[cmpt_type]
    except KeyError as e:
        return not_implemented

def not_implemented(cmpt):
    """Placeholder function for component parsers that are not implemented"""
    parsed = UNKNOWN_COMPONENT.copy()
    parsed['type'] = classify_type(cmpt)
    parsed['error'] = 'not implemented'
    return [parsed]


def extract_results_column(soup):
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        list: a list of HTML result components
    """
    # Check if layout contains left side bar
    left_side_bar = soup.find('div', {'class': 'OeVqAd'})
    rso = soup.find('div', {'id':'rso'})

    if not left_side_bar and rso:
        # Extract results from single div
        drop_tags = {'script', 'style', None}
        column = [('main', c) for c in rso.children if c.name not in drop_tags]

    else:
        # Extract results from two div sections
        rso = []
        # rso = soup.find('div', {'id':'rso'})

        # Find section 1 results and append to rso list
        section1 = soup.find_all('div', {'class':'sATSHe'})
        # section1 = soup.find_all('div', {'class':'UDZeY OTFaAf'})
        for div in section1:

            # Conditional handling for Twitter result
            if div.find('h2') and div.find('h2').text == "Twitter Results": 
                rso.append(div.find('div').parent)

            # Conditional handling for g-section with header
            elif div.find('g-section-with-header'): 
                rso.append(div.find('g-section-with-header').parent)

            # Include divs with a "View more" type of button
            elif div.find('g-more-link'): 
                rso.append(div)

            # Include footer components that appear in the main column
            elif div.find('div', {'class':'oIk2Cb'}):
                rso.append(div)

            else:
                # Handle general results
                for child in div.find_all('div',  {'class':'g'}): 
                    rso.append(child)

        # Find section 2 results and append to rso list
        section2 = soup.find('div', {'class':'WvKfwe a3spGf'})
        if section2:
            for child in section2.children:
                rso.append(child)

        drop_tags = {'script', 'style'}
        column = [('main', c) for c in rso if c.name not in drop_tags]

    # Legacy parsing
    # div_class = {'class':['g','bkWMgd']}
    # column = [('main', r) for r in soup.find_all('div', div_class)]

    # Hacky fix removing named Twitter component without content, possible G error
    # Another fix for empty components, e.g. - <div class="bkWMgd"></div>
    drop_text = {'Twitter Results', ''}
    column = [(cloc, c) for (cloc, c) in column if c.text not in drop_text]
    return column
    

def extract_components(soup):
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        list: a rank ordered top-to-bottom and left-to-right list of 
             (component location, component soup) tuples
    """

    cmpts = []

    # Top Image Carousel
    top_bar = soup.find('div', {'id':'appbar'})
    if top_bar:
        has_img = top_bar.find(lambda tag: tag.has_attr('src') and not tag.has_attr('data-src'))
        if top_bar.find('g-scrolling-carousel') and has_img:
            cmpts.append(('top_image_carousel', top_bar))

    # Shopping Ads
    shopping_ads = soup.find('div', {'class': 'commercial-unit-desktop-top'})
    if shopping_ads:
        cmpts.append(('shopping_ad', shopping_ads))

    # Top Ads
    ads = soup.find('div', {'id':'tads'})
    if ads: 
        cmpts.append(('ad', ads))

    column = extract_results_column(soup)
    cmpts.extend(column)

    # Bottom Ads
    ads = soup.find('div', {'id':'tadsb'})
    if ads:
        cmpts.append(('ad', ads))

    # Footer results
    footer = extract_footer(soup)
    if footer and extract_footer_components(footer):
        cmpts.append(('footer', footer))

    # RHS Knowledge Panel 
    rhs = soup.find('div', {'id': 'rhs'})
    if rhs:
        rhs_kp = rhs.find('div', {'class': ['kp-wholepage', 'knowledge-panel']})
        if rhs_kp:
            # reading from top-to-bottom, left-to-right
            cmpts.append(('knowledge_rhs', rhs_kp))
            
    return cmpts

def parse_component(cmpt, cmpt_type='', cmpt_rank=0):
    """Parse a SERP component
    
    Args:
        cmpt (bs4 object): A parsed SERP component
        cmpt_type (str, optional): The type of component it is
        cmpt_rank (int, optional): The rank the component was found
    
    Returns:
        dict: The parsed results and/or subresults
    """
    # Classify Component
    cmpt_type = cmpt_type if cmpt_type else classify_type(cmpt)
    assert cmpt_type, 'Null component type'

    # if cmpt_type == 'directions':
    #     print(cmpt)

    # Return unknown components
    if cmpt_type == 'unknown':
        unknown_component = UNKNOWN_COMPONENT.copy()
        unknown_component['cmpt_rank'] = 0
        return [unknown_component]

    # Parse component
    try:
        parser = get_component_parser(cmpt_type)
        parsed_cmpt = parser(cmpt)
        
        # Add cmpt rank to parsed
        if isinstance(parsed_cmpt, list):
            for sub_rank, sub in enumerate(parsed_cmpt):
                sub.update({'sub_rank':sub_rank, 'cmpt_rank':cmpt_rank})
        else:
            parsed_cmpt.update({'sub_rank':0, 'cmpt_rank':cmpt_rank})

    except Exception:
        log.exception('Parsing Exception')
        err = traceback.format_exc()
        return [{'type':cmpt_type, 'cmpt_rank':cmpt_rank, 'error':err}]

    return parsed_cmpt

def parse_serp(serp, serp_id=None, crawl_id=None, verbose=False, make_soup=False):
    """Parse a Search Engine Result Page (SERP)
    
    Args:
        serp (html): raw SERP HTML or BeautifulSoup
        serp_id (str, optional): A SERP-level key, hash generated by default
        verbose (bool, optional): Log details about each component parse
    
    Returns:
        list: A list of parsed results ordered top-to-bottom and left-to-right
    """

    soup = webutils.make_soup(serp) if make_soup else serp
    assert type(soup) is BeautifulSoup, 'Input must be BeautifulSoup'

    # Set SERP-level attributes
    serp_attrs = {
        'crawl_id':crawl_id, 
        'serp_id':serp_id, 
        'qry': parse_query(soup),
        'lang': parse_lang(soup),
        'lhs_bar': soup.find('div', {'class': 'OeVqAd'}) is not None,
    }
    
    # Extract components
    cmpts = extract_components(soup)

    # Classify and parse components
    parsed = []
    if verbose: 
        log.info(f'Parsing SERP {serp_id}')
        
    for cmpt_rank, (cmpt_loc, cmpt) in enumerate(cmpts):
        cmpt_type = classify_type(cmpt) if cmpt_loc == 'main' else cmpt_loc
        if cmpt_type == 'directions':
            # print(cmpt)
            pass
        if verbose: 
            log.info(f'{cmpt_rank} | {cmpt_type}')
        parsed_cmpt = parse_component(cmpt, cmpt_type=cmpt_type, cmpt_rank=cmpt_rank)
        assert isinstance(parsed_cmpt, list), \
            f'Parsed component must be list: {parsed_cmpt}'
        parsed.extend(parsed_cmpt)

    for serp_rank, p in enumerate(parsed):
        p['serp_rank'] = serp_rank
        p.update(serp_attrs)
        
    return parsed
