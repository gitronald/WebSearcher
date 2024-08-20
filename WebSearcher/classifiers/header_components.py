from .. import webutils
import bs4


class ClassifyHeaderComponent:
    """Classify a component from the header section based on its bs4.element.Tag"""

    @staticmethod
    def classify(cmpt: bs4.element.Tag) -> str:
        """Classify the component type based on header text"""
        
        cmpt_type = "unknown"
        if webutils.check_dict_value(cmpt.attrs, "id", ["taw", "topstuff"]):
            cmpt_type = "notice"
        return cmpt_type
