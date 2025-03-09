import bs4

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
        header_dict = ClassifyHeaderText._get_header_level_mapping(level)

        # Collect list of potential header divs
        header_list = []
        header_list.extend(cmpt.find_all(f"h{level}", {"role":"heading"}))
        header_list.extend(cmpt.find_all(f"h{level}", {"class":["O3JH7", "q8U8x", "mfMhoc"]}))
        header_list.extend(cmpt.find_all("div", {"aria-level":f"{level}", "role":"heading"}))
        header_list.extend(cmpt.find_all("div", {"aria-level":f"{level}", "class":"XmmGVd"}))

        # Check header text for known title matches
        for header in filter(None, header_list):
            for text, label in header_dict.items():
                if label == "local_results" and text == "locations":
                    if header.text.strip().endswith(text):
                        return label
                if header.text.strip().startswith(text):
                    return label

        return "unknown"

    @staticmethod
    def _get_header_level_mapping(level) -> dict:
        """Return mapping of header level to header text"""
        options = {2: ClassifyHeaderText.TYPE_TO_H2_MAPPING,
                   3: ClassifyHeaderText.TYPE_TO_H3_MAPPING}
        return options.get(level, {})

    # WS type -> header level 2 text (e.g., <h2>title</h2>)
    TYPE_TO_H2_MAPPING = {
        "directions": ["Directions", 
                       "Ubicaciones"],
        "discussions_and_forums": ["Discussions and forums"],
        "general": ["Complementary Results", 
                    "Web Result with Site Links", 
                    "Web results", 
                    "Resultados de la Web", 
                    "AI-powered overview", 
                    "Visión general creada por IA", 
                    "Things to know", 
                    "Cosas que debes saber"],
        "images": ["Images", 
                   "Imágenes"],
        "jobs": ["Jobs", 
                 "Empleos"],
        "knowledge": ["Calculator Result", 
                      "Featured snippet from the web", "Fragmento destacado",
                      "Finance Results", "Resumen de Mercado",
                      "From sources across the web", 
                      "Knowledge Result", 
                      "Resultado de traducci\u00f3n", 
                      "Sports Results", 
                      "Table", "Posiciones",
                      "Stat Leaders", "Líderes de estadísticas",
                      "Teams", "Equipos",
                      "Players", "Jugadores",
                      "Translation Result", 
                      "Unit Converter", 
                      "Weather Result", "Clima",
                      "Artworks", "Obras de arte",
                      "Songs", "Canciones",
                      "Albums", "Álbumes",
                      "What people are saying",
                      "About", "Información",
                      "Profiles", "Perfiles"],
        "local_news": ["Local news", "Noticias Locales"],
        "local_results": [
            "Local Results",
            "Locations",
            "Places", "Sitios"
            "Businesses",
            "locations",
        ],
        "map_results": ["Map Results",
                        "Choice Hotels", 
                        "Hoteles", 
                        "Hotel"],
        "omitted_notice": ["Notices about Filtered Results"],
        "people_also_ask": ["People also ask", "Más preguntas"],
        "perspectives": ["Perspectives & opinions", 
                         "Perspectives"],
        "searches_related": ["Additional searches", 
                             "More searches", "Ver más",
                             "Other searches", 
                             "People also search for", "También se buscó",
                             "Related", 
                             "Related searches", 
                             "Related to this search",
                             "Searches related to"],
        "top_stories": ["Top stories", 
                        "Noticias Destacadas", 
                        "Noticias Principales",
                        "News", 
                        "Noticias",
                        "Market news"],
        "twitter": ["Twitter Results"],
        "videos": ["Videos"]
    }

    # WS type -> header level 2 text (e.g., <h3>title</h3>)
    TYPE_TO_H3_MAPPING = {
        "images": ["Images for"],
        "latest_from": ["Latest from"],
        "products": ["Popular products"],
        "news_quotes": ["Quotes in the news"],
        "recipes": ["Recipes", "Recetas"],
        "searches_related": ["Related searches"],
        "scholarly_articles": ["Scholarly articles for", "Artículos académicos para"],
        "top_stories": ["Top stories", "Noticias destacadas", "Noticias Principales"],
        "videos": ["Videos"],
        "view_more_news": ["View more news", "Más noticias", "Ver más"],
        "view_more_videos": ["View more videos", "Más videos", "Ver más"]
    }

    # Invert from {label: [text, ...]} to [{text: label}, ...]
    TYPE_TO_H2_MAPPING = {vv: k for k, v in TYPE_TO_H2_MAPPING.items() for vv in v}
    TYPE_TO_H3_MAPPING = {vv: k for k, v in TYPE_TO_H3_MAPPING.items() for vv in v}

