from .top_stories import parse_top_stories

def parse_recent_posts(cmpt):
    """Parse a "Recent posts" component

    These components have a similar carousel as Top Stories and Perspectives.
    
    Args:
        cmpt (bs4 object): A html component
    
    Returns:
        dict : parsed result
    """
    return parse_top_stories(cmpt, ctype='recent_posts')
