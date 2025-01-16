import bs4
from .. import webutils
from .main import ClassifyMain

class ClassifyFooter:

    @staticmethod
    def classify(cmpt: bs4.element.Tag) -> str:
        layout_conditions = [
            ('id' in cmpt.attrs and cmpt.attrs['id'] in {'bres', 'brs'}),
            ('class' in cmpt.attrs and cmpt.attrs['class'] == ['MjjYud']),
        ]

        # Ordered list of classifiers to try
        if any(layout_conditions):
            classifier_list = [
                ClassifyMain.img_cards,
                ClassifyFooter.discover_more,
                ClassifyFooter.searches_related,
            ]
        else:
            classifier_list = [
                ClassifyFooter.omitted_notice,
            ]

        # Default unknown, exit on first successful classification
        cmpt_type = "unknown"
        for classifier in classifier_list:
            if cmpt_type != "unknown":  break
            cmpt_type = classifier(cmpt)

        # Fall back to main classifier
        if cmpt_type == 'unknown':
            cmpt_type = ClassifyMain.classify(cmpt)
        
        return cmpt_type

    @staticmethod
    def discover_more(cmpt):
        conditions = [
            cmpt.find("g-scrolling-carousel"),
        ]
        return 'discover_more' if all(conditions) else "unknown"

    @staticmethod
    def omitted_notice(cmpt):
        conditions = [
            cmpt.find("p", {"id":"ofr"}),
            (webutils.get_text(cmpt, "h2") == "Notices about Filtered Results"),
        ]
        return "omitted_notice" if any(conditions) else "unknown"

    @staticmethod
    def searches_related(cmpt):
        known_labels = {'Related', 
                        'Related searches', 
                        'People also search for', 
                        'Related to this search',
                        'Searches related to'}
        h3 = cmpt.find('h3')
        h3_matches = [h3.text.strip().startswith(text) for text in known_labels] if h3 else []
        return 'searches_related' if any(h3_matches) else 'unknown'
