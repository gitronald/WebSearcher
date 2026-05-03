import bs4

from ..component_types import header_text_to_type


class ClassifyHeaderText:
    """Classify components based on header text (e.g. <h2>title</h2>)"""

    @staticmethod
    def classify(cmpt: bs4.element.Tag, levels: list[int] = [2, 3]) -> str:
        for level in levels:
            header = ClassifyHeaderText._classify_header(cmpt, level)
            if header != "unknown":
                return header
        return "unknown"

    @staticmethod
    def classify_header_lvl2(cmpt: bs4.element.Tag) -> str:
        return ClassifyHeaderText._classify_header(cmpt, level=2)

    @staticmethod
    def classify_header_lvl3(cmpt: bs4.element.Tag) -> str:
        return ClassifyHeaderText._classify_header(cmpt, level=3)

    @staticmethod
    def _classify_header(cmpt: bs4.element.Tag, level: int) -> str:
        """Check text in common headers for dict matches"""
        header_dict = header_text_to_type(level)

        # Lazy generator over potential header divs (defers find_all until iterated)
        selectors = [
            {"name": f"h{level}", "attrs": {"role": "heading"}},
            {"name": f"h{level}", "attrs": {"class": ["O3JH7", "q8U8x", "mfMhoc"]}},
            {"attrs": {"aria-level": f"{level}", "role": "heading"}},
        ]
        headers = (h for sel in selectors for h in cmpt.find_all(**sel))

        # Check header text for known title matches
        for header in filter(None, headers):
            for text, label in header_dict.items():
                if label == "local_results" and text == "locations":
                    if header.text.strip().endswith(text):
                        return label
                if header.text.strip().startswith(text):
                    return label

        return "unknown"
