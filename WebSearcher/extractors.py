from .component_parsers.footer import extract_footer, extract_footer_components

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
        column = []
        for child in rso.children:
            if child.name in drop_tags:
                continue
            if not child.attrs:
                column.extend(child.contents)
            else:
                column.append(child)
        column = list(zip(['main']*len(column), column))

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

    # Legacy extraction
    # div_class = {'class':['g','bkWMgd']}
    # column = [('main', r) for r in soup.find_all('div', div_class)]

    # Remove empty rso component; hidden <h2> header
    drop_text = {"Main results"}
    column = [(cloc, c) for (cloc, c) in column if c.text not in drop_text]

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
