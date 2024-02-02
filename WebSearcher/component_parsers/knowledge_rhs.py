def parse_knowledge_rhs(cmpt, sub_rank=0):
    """Parse the Right-Hand-Side Knowledge Panel

    Args:
        cmpt (bs4 object): a right-hand-side knowledge component

    Returns:
        list: Return parsed dictionary in a list
    """
    parsed_list = parse_knowledge_rhs_main(cmpt)
    description = cmpt.find('h2', {'class': 'Uo8X3b'})
    if description and description.parent:
        subs = [s for s in description.parent.next_siblings]
        parsed_subs = [
            parse_knowledge_rhs_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)
        ]
        parsed_list.extend(parsed_subs)
    return parsed_list


def parse_knowledge_rhs_main(cmpt, sub_rank=0):
    """Parse the Right-Hand-Side Knowledge Panel main component"""

    parsed = {
        'type': 'knowledge',
        'sub_type': 'panel_rhs',
        'sub_rank': sub_rank,
        'title': '',
        'text': '',
        'url': '',
        'details': {},
        'rhs_column': True
    }

    # images
    if cmpt.find('h3') and cmpt.find('h3').text == 'Images':
        sibling = cmpt.find('h3').next_sibling
        if sibling:
            imgs = sibling.find_all('a')
            parsed['details']['img_urls'] = [
                img['href'] for img in imgs if 'href' in img.attrs
            ]

    # title, subtitle
    if cmpt.find('h2', {'data-attrid': 'title'}):
        parsed['title'] = cmpt.find('h2', {'data-attrid': 'title'}).text
    if cmpt.find('div', {'data-attrid': 'subtitle'}):
        parsed['details']['subtitle'] = cmpt.find(
            'div', {'data-attrid': 'subtitle'}
        ).text

    # description
    description = cmpt.find('h2', {'class': 'Uo8X3b'})
    if description and description.parent:
        if description.parent.find('span'):
            parsed['text'] = description.parent.find('span').text
        if (
            description.parent.find('a')
            and 'href' in description.parent.find('a').attrs
        ):
            parsed['url'] = description.parent.find('a')['href']

    description = cmpt.find('div', {'class': 'kno-rdesc'})
    if description:
        parsed['text'] = description.find('span').text
        if description.find('a') and 'href' in description.find('a').attrs:
            parsed['url'] = description.find('a')['href']

    # submenu
    if description and description.parent:
        alinks = description.parent.find_all('a')
        if description.parent.previous_sibling:
            alinks += description.parent.previous_sibling.find_all('a')
        if len(alinks) > 1:  # 1st match has main description
            parsed['details']['urls'] = [
                parse_alink(a) for a in alinks[1:] if 'href' in a.attrs
            ]

    if not len(parsed['details']):
        parsed['details'] = None

    return [parsed]


def parse_knowledge_rhs_sub(sub, sub_rank=0):
    """Parse a Right-Hand-Side Knowledge Panel subcomponent"""

    parsed = {
        'type': 'knowledge',
        'sub_type': 'panel_rhs',
        'sub_rank': sub_rank + 1,
        'title': '',
        'details': None,
        'rhs_column': True
    }

    heading = sub.find('div', {'role': 'heading'})
    if heading:
        parsed['title'] = heading.get_text(' ')

    alinks = sub.find_all('a')
    if alinks:
        parsed['details'] = [parse_alink(a) for a in alinks if 'href' in a.attrs]

    return parsed


def parse_alink(a):
    return {'url': a['href'], 'text': a.text}
