from .component_parsers.footer import extract_footer, extract_footer_components
from . import logger
log = logger.Logger().start(__name__)

from bs4 import BeautifulSoup


def check_page_layout(soup: BeautifulSoup) -> dict:
    """Check SERP layout elements
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        dict: a dictionary with keys 'left-bar' and 'top-bar' and boolean values
    """
    log.debug(f"Checking page layout")
    layout_dict = {
        'rso': soup.find('div', {'id':'rso'}),                # main results
        'left-bar': soup.find('div', {'class': 'OeVqAd'}),    # left side bar
        'top-bar-1': soup.find('div', {'class': 'M8OgIe'}),   # top bar
        'top-bar-2': soup.find('div', {'class': 'XqFnDf'}),   # top bar
    }
    layout_dict['top-bar'] = layout_dict['top-bar-1'] or layout_dict['top-bar-2']

    return layout_dict


def extract_results_column(soup: BeautifulSoup, drop_tags: set = {'script', 'style', None}) -> list:
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        list: a list of HTML result components
    """
    log.debug(f"Extracting Results")
    layout_dict = check_page_layout(soup)

    if layout_dict['rso']:

        if not layout_dict['top-bar'] and not layout_dict['left-bar']:
            log.debug("layout: standard")
            column = extract_children(layout_dict['rso'], drop_tags)

        elif layout_dict['top-bar']:
            log.debug("layout: top-bar")
            column = extract_from_top_bar(layout_dict, drop_tags)
            
        elif layout_dict['left-bar']:
            # Not implemented - may appear in pre-2022 data
            log.debug("layout: left-bar")
            column = []
        
    else:
        log.debug("layout: no-rso")
        column = extract_from_no_rso(soup, drop_tags)

    # Drop empty components
    drop_text = {
        "Main results",    # Remove empty rso component; hidden <h2> header  
        "Twitter Results", # Remove empty Twitter component
        "",                # Remove empty divs
    }
    column = [c for c in column if c.text not in drop_text]
    column = list(zip(['main']*len(column), column))

    return column


def extract_children(soup: BeautifulSoup, drop_tags: set = {}) -> list:
    """Extract children from BeautifulSoup, drop specific tags, flatten list"""
    children = []
    for child in soup.children:
        if child.name in drop_tags:
            continue
        if not child.attrs:
            children.extend(child.contents)
        else:
            children.append(child)
    return children


def extract_from_top_bar(layout_dict: dict, drop_tags: set = {}) -> list:
    """Extract components from top bar layout"""
    column = layout_dict['rso'].find_all('div', {'class':'sATSHe'})
    if column:
        log.debug("format: top-bar-sATSHe")
        column = [c for c in column if c.name not in drop_tags]
    else:
        log.debug("format: top-bar-children")
        column = extract_children(layout_dict['rso'], drop_tags)

    # Combine with top bar
    column = [layout_dict['top-bar']] + column
    return column


def extract_from_no_rso(soup: BeautifulSoup, drop_tags: set = {}) -> list:
    """Extract components from no-rso layout"""
    column = []
    section1 = soup.find_all('div', {'class':'UDZeY OTFaAf'})
    for div in section1:

        # Conditional handling for Twitter result
        if div.find('h2') and div.find('h2').text == "Twitter Results": 
            column.append(div.find('div').parent)

        # Conditional handling for g-section with header
        elif div.find('g-section-with-header'): 
            column.append(div.find('g-section-with-header').parent)

        # Include divs with a "View more" type of button
        elif div.find('g-more-link'): 
            column.append(div)

        # Include footer components that appear in the main column
        elif div.find('div', {'class':'oIk2Cb'}):
            column.append(div)

        else:
            # Handle general results
            for child in div.find_all('div',  {'class':'g'}): 
                column.append(child)

        # Find section 2 results and append to column list
        section2 = soup.find('div', {'class':'WvKfwe a3spGf'})
        if section2:
            for child in section2.children:
                column.append(child)
        column = [c for c in column if c.name not in drop_tags]
    
    return column


def extract_components(soup: BeautifulSoup) -> list:
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        list: a rank ordered top-to-bottom and left-to-right list of 
             (component location, component soup) tuples
    """

    cmpts = []

    # RHS Knowledge Panel - extract (removes from soup, must be done first)
    has_rhs = soup.find('div', {'id': 'rhs'})
    if has_rhs:
        rhs = soup.find('div', {'id': 'rhs'}).extract()

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

    # Main Results
    column = extract_results_column(soup)
    cmpts.extend(column)

    # Bottom Ads
    ads = soup.find('div', {'id':'tadsb'})
    if ads:
        cmpts.append(('ad', ads))

    # Footer Results
    footer = extract_footer(soup)
    if footer and extract_footer_components(footer):
        cmpts.append(('footer', footer))
    
    # RHS Knowledge Panel - append
    if has_rhs:
        rhs_kp = rhs.find('div', {'class': ['kp-wholepage', 'knowledge-panel', 'TzHB6b']})
        if rhs_kp:
            # reading from top-to-bottom, left-to-right
            cmpts.append(('knowledge_rhs', rhs_kp))

    return cmpts
