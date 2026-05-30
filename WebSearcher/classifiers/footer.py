from selectolax.lexbor import LexborNode as Node

from .._slx import class_tokens, get_text
from .main import ClassifyMain


class ClassifyFooter:
    @staticmethod
    def classify(cmpt: Node) -> str:
        node: Node = cmpt
        attrs = node.attributes
        layout_conditions = [
            "id" in attrs and attrs["id"] in {"bres", "brs"},
            "class" in attrs and class_tokens(node) == ["MjjYud"],
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

        cmpt_type = "unknown"
        for classifier in classifier_list:
            if cmpt_type != "unknown":
                break
            cmpt_type = classifier(node)

        # Fall back to main classifier
        if cmpt_type == "unknown":
            cmpt_type = ClassifyMain.classify(node)

        return cmpt_type

    @staticmethod
    def discover_more(cmpt: Node) -> str:
        return "discover_more" if cmpt.css_first("g-scrolling-carousel") is not None else "unknown"

    @staticmethod
    def omitted_notice(cmpt: Node) -> str:
        if cmpt.css_first('p[id="ofr"]') is not None:
            return "omitted_notice"
        h2 = cmpt.css_first("h2")
        if h2 is not None and (get_text(h2) or "") == "Notices about Filtered Results":
            return "omitted_notice"
        return "unknown"

    @staticmethod
    def searches_related(cmpt: Node) -> str:
        node = cmpt
        known_labels = {
            "Related",
            "Related searches",
            "People also search for",
            "Related to this search",
            "Searches related to",
        }
        h3 = node.css_first("h3")
        if h3 is None:
            return "unknown"
        text = (get_text(h3) or "").strip()
        return (
            "searches_related"
            if any(text.startswith(label) for label in known_labels)
            else "unknown"
        )
