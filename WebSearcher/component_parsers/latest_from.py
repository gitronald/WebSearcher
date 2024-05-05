from .top_stories import parse_top_stories

def parse_latest_from(cmpt):
    """Parse a "Latest news" component

    These components are the same as Top Stories, but have a different heading.
    
    Args:
        cmpt (bs4 object): A latest from component
    
    Returns:
        dict : parsed result
    """
    return parse_top_stories(cmpt, ctype='latest_from')
