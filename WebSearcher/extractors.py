from .component_parsers.footer import extract_footer, extract_footer_components

def extract_results_column(soup):
    """Extract SERP components
    
    Args:
        soup (bs4): BeautifulSoup SERP
    
    Returns:
        list: a list of HTML result components
    """

    # Drop tags
    drop_tags = {'script', 'style', None}

    # Check if layout contains left side bar
    layout_shift = [
        soup.find('div', {'class': 'OeVqAd'}),  # left side bar
        soup.find('div', {'class': 'M8OgIe'}),  # top bar
    ]
    rso = soup.find('div', {'id':'rso'})
    column = []

    if not any(layout_shift) and rso:
        for child in rso.children:
            if child.name in drop_tags:
                continue
            if not child.attrs:
                column.extend(child.contents)
            else:
                column.append(child)
    elif rso:
        # Extract results from two div sections

        # Find section 1 results and append to rso list
        column = rso.find_all('div', {'class':'sATSHe'})
        column = [c for c in column if c.name not in drop_tags]

    else:
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

    # Drop empty components
    drop_text = {
        "Main results",    # Remove empty rso component; hidden <h2> header  
        "Twitter Results", # Remove empty Twitter component
        "",                # Remove empty divs
    }
    column = [c for c in column if c.text not in drop_text]
    column = list(zip(['main']*len(column), column))


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
