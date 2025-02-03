from .components import Component, ComponentList
from . import utils
from . import webutils
from . import logger
log = logger.Logger().start(__name__)
import bs4


class Extractor:
    def __init__(self, soup: bs4.BeautifulSoup):
        self.soup = soup
        self.components = ComponentList()
        self.rhs = {}
        self.layout_divs = {
            "rso": None,
            "top-bars": None,
            "left-bar": None,
        }
        self.layouts = {
            "rso": False,
            "top-bars": False,
            "left-bar": False,
            "standard": False,
            "no-rso": False,
        }
        self.layout_label = None
        self.layout_extractors = {
            "standard": self.extract_from_standard,
            "top-bars": self.extract_from_top_bar,
            "left-bar": self.extract_from_left_bar,
            "no-rso": self.extract_from_no_rso
        }

    def extract_components(self):
        log.debug("Extracting Components")
        self.extract_rhs()
        self.extract_header()
        self.extract_main()
        self.extract_footer()
        self.append_rhs()
        log.debug(f"Extracted {self.components.cmpt_rank_counter:,} components")

    # --------------------------------------------------------------------------
    # Right Hand Sidebar Components
    # --------------------------------------------------------------------------

    def extract_rhs(self):
        """Extract the Right Hand Side (RHS) Knowledge Panel. Can appear in arbitrary order, must extract first."""
        rhs_kws = ('div', {'id': 'rhs'})
        rhs = self.soup.find(*rhs_kws).extract() if self.soup.find(*rhs_kws) else None
        if rhs:
            rhs_layouts = {
                'rhs_complementary': rhs if webutils.check_dict_value(rhs.attrs, "role", "complementary") else None,
                'rhs_knowledge': rhs.find('div', {'class': ['kp-wholepage', 'knowledge-panel', 'TzHB6b']}),
            }
            rhs_layout = next((layout for layout, component in rhs_layouts.items() if component), None)
            if rhs_layout:
                log.debug(f"rhs_layout: {rhs_layout}")
                self.rhs = {"elem": rhs_layouts[rhs_layout], 
                            "section": "rhs", 
                            "type": "knowledge_rhs"}
            else:
                log.debug(f"no rhs_layout")


    def append_rhs(self):
        """Append the RHS Knowledge Panel to the components list at the end"""
        if self.rhs:
            log.debug(f"appending rhs")
            self.components.add_component(**self.rhs)
            self.rhs = None


    # --------------------------------------------------------------------------
    # Header Components
    # --------------------------------------------------------------------------

    def extract_header(self):
        """Extract the header section, often a carousel of images or other suggestions."""
        self.extract_top_bar()
        self.extract_notices()


    def extract_top_bar(self):
        """Extract the top bar section, often a carousel of images or other suggestions."""
        top_bar = self.soup.find('div', {'id':'appbar'})
        if top_bar:
            has_img = top_bar.find(lambda tag: tag.has_attr('src') and not tag.has_attr('data-src'))
            if top_bar.find('g-scrolling-carousel') and has_img:
                self.components.add_component(top_bar, section='header', type='top_image_carousel')


    def extract_notices(self):
        """Append notices to the components list at the end"""
        notices = webutils.find_all_divs(self.soup, "div", {"id": "oFNiHe"})
        notices = webutils.filter_empty_divs(notices)
        log.debug(f"notices: {len(notices)}")
        for notice in notices:
            self.components.add_component(notice, section="header", type="notice")

    # --------------------------------------------------------------------------
    # Main Components
    # --------------------------------------------------------------------------

    def extract_main(self):
        """Extract the main results sections of the SERP"""
        # self.extract_main_shopping_ads()
        self.extract_main_ads_top()
        self.extract_main_components()
        self.extract_main_ads_bottom()


    # def extract_main_shopping_ads(self):
    #     """Extract the main shopping ads section of the SERP"""
    #     shopping_ads = self.soup.find('div', {'class': 'commercial-unit-desktop-top'})
    #     if shopping_ads:
    #         self.components.add_component(shopping_ads, section='main', type='shopping_ads')


    def extract_main_ads_top(self):
        """Extract the main ads section of the SERP"""
        ads = self.soup.find('div', {'id':'tads'})
        if ads and webutils.get_text(ads):
            # Filter if already extracted as shopping ads
            # if not ads.find('div', {'class': 'commercial-unit-desktop-top'}):
            self.components.add_component(ads, section='main', type='ad')


    def extract_main_components(self, drop_tags: set={'script', 'style', None}):
        """Extract main components based on SERP layout"""
        log.debug("Extracting main column components")
        self.check_layout_main()
        try:
            layout_extractor = self.layout_extractors[self.layout_label]
            column = layout_extractor(drop_tags)
            for component in column:
                if Extractor.is_valid_main_component(component):
                    self.components.add_component(component, section='main')
        except KeyError:
            raise ValueError(f"no extractor for layout_label: {self.layout_label}")    
        log.debug(f"Extracted main components: {self.components.cmpt_rank_counter:,}")


    def extract_main_ads_bottom(self):
        """Extract the main ads section of the SERP"""
        ads = self.soup.find('div', {'id':'tadsb'})
        if ads and webutils.get_text(ads):
            self.components.add_component(ads, section='main', type='ad')

    # --------------------------------------------------------------------------
    # Layout Specifics
    # --------------------------------------------------------------------------


    def check_layout_main(self):
        """Divide and label the page layout"""
        log.debug(f"Checking SERP layout")

        # Layout soup subsets
        self.layout_divs['rso'] = self.soup.find('div', {'id':'rso'})
        self.layout_divs['left-bar'] = self.soup.find('div', {'class': 'OeVqAd'})
        self.layout_divs['top-bars'] = self.soup.find_all('div', {'class': ['XqFnDf', 'M8OgIe']})
        
        # Layout classifications
        self.layouts['rso'] = bool(self.layout_divs['rso'])
        self.layouts['top-bars'] = bool(self.layout_divs['top-bars'])
        self.layouts['left-bar'] = bool(self.layout_divs['left-bar'])
        self.layouts['standard'] = (self.layouts['rso'] &
                                    (not self.layouts['top-bars']) &
                                    (not self.layouts['left-bar']))
        self.layouts['no-rso'] = not self.layouts['rso']

        # Get layout label
        label_matches = [k for k,v in self.layouts.items() if k !='rso' and v]
        first_match = label_matches[0] if label_matches else None
        self.layout_label = first_match
        log.debug(f"layout: {self.layout_label}")
    

    def extract_from_standard(self, drop_tags: set = {}) -> list:

        if self.layout_divs['rso'].find('div', {'id':'kp-wp-tab-overview'}):
            log.debug("layout update: standard-alt-1")
            self.layout_label = 'standard-alt'
            column = self.layout_divs['rso'].find_all('div', {'class':'TzHB6b'})
            return column
        
        column = Extractor.extract_children(self.layout_divs['rso'], drop_tags)
        column = [c for c in column if Extractor.is_valid_main_component(c)]
        
        if len(column) == 0:
            log.debug("layout update: standard-alt-0")
            self.layout_label = 'standard-alt'
            divs = self.layout_divs['rso'].find_all('div', {'id':'kp-wp-tab-overview'})
            column = sum([div.find_all('div', {'class':'TzHB6b'}) for div in divs], [])
        return column


    def extract_from_top_bar(self, drop_tags: set = {}) -> list:
        """Extract components from top-bars layout"""
        column = []

        top_bar_divs = Extractor.extract_from_top_bar_divs(self.layout_divs['top-bars'])
        column.extend(top_bar_divs)
        
        rso_layout_divs = self.layout_divs['rso'].find_all('div', {'class':'sATSHe'})
        if rso_layout_divs:
            self.layout_label = 'top-bars-divs'
            layout_column = [div for div in rso_layout_divs if div.name not in drop_tags]
        else:
            self.layout_label = 'top-bars-children'
            layout_column = Extractor.extract_children(self.layout_divs['rso'], drop_tags)
        log.debug(f"layout update: {self.layout_label}")

        column.extend(layout_column)
        return column
    
    @staticmethod
    def extract_from_top_bar_divs(soup, drop_tags: set = {}) -> list:
        output_list = []
        for top_bar in soup:
            if webutils.check_dict_value(top_bar.attrs, "class", ["M8OgIe"]):
                knowledge_divs = webutils.find_all_divs(top_bar, "div", {"jscontroller": ["qTdDb", "OWrb3e"]})
                output_list.extend(knowledge_divs)
                log.debug(f"layout: M8OgIe divs: {len(knowledge_divs)}")
            else:
                output_list.append(top_bar)
        return output_list


    def extract_from_left_bar(self, drop_tags: set = {}) -> list:
        """Extract components from left-bar layout"""
        column = self.soup.find_all('div', {'class':'TzHB6b'})
        return column


    def extract_from_no_rso(self, drop_tags: set = {}) -> list:
        """Extract components from no-rso layout"""
        log.debug("layout: no-rso")
        column = []
        section1 = self.soup.find_all('div', {'class':'UDZeY OTFaAf'})
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
            section2 = self.soup.find('div', {'class':'WvKfwe a3spGf'})
            if section2:
                for child in section2.children:
                    column.append(child)
            column = [c for c in column if c.name not in drop_tags]
        return column


    @staticmethod
    def extract_children(soup: bs4.BeautifulSoup, drop_tags: set = {}) -> list:
        """Extract children from BeautifulSoup, drop specific tags, flatten list"""
        log.debug("layout: extracting children")
        children = []
        for child in soup.children:
            if child.name in drop_tags:
                continue
            if not child.attrs:
                children.extend(child.contents)
            else:
                children.append(child)
        return children


    @staticmethod
    def is_valid_main_component(c) -> bool:
        """Check if a given component is neither empty nor a hidden survey"""
        if not c:
            return False
        else:
            drop_text = {
                "Main results",    # Remove empty rso component; hidden <h2> header  
                "Twitter Results", # Remove empty Twitter component
                "",                # Remove empty divs
            }
            return c.text not in drop_text and not Extractor.is_hidden_survey(c)

    @staticmethod
    def is_hidden_survey(element):
        """Check if a component is a hidden survey component; no visual presence so filter out"""
        conditions = [
            element.find('promo-throttler'),
            webutils.check_dict_value(element.attrs, "class", ["ULSxyf"]),
        ]
        return all(conditions)


    # --------------------------------------------------------------------------
    # Footer Components
    # --------------------------------------------------------------------------


    def extract_footer(self):
        """Extract the footer section of the SERP"""
        log.debug("extracting footer components")

        footer_div = self.soup.find('div', {'id':'botstuff'})
        footer_component_list = []

        # Check if footer div exists
        if footer_div:
            footer_component_divs = webutils.find_all_divs(self.soup, 'div', {'id':['bres', 'brs']}) 
            if footer_component_divs:
                log.debug(f"found footer components: {len(footer_component_divs):,}")

                # Expand components by checking for nested divs
                for footer_component_div in footer_component_divs:
                    expanded_divs = webutils.find_all_divs(footer_component_div, "div", {"class":"MjjYud"})
                    if expanded_divs and len(expanded_divs) > 1:
                        footer_component_list.extend(expanded_divs)
                    else:
                        footer_component_list.append(footer_component_div)

        # Check for omitted notice
        omitted_notice = self.soup.find('div', {'class':'ClPXac'})
        if omitted_notice:
            footer_component_list.append(omitted_notice)

        footer_component_list = [e for e in footer_component_list if not Extractor.is_hidden_footer(e)]
        log.debug(f'footer_component_list len: {len(footer_component_list)}')
        
        for footer_component in footer_component_list:
            self.components.add_component(footer_component, section='footer')


    @staticmethod
    def is_hidden_footer(element):
        """Check if a component is a hidden footer component; no visual presence so filter out"""
        conditions = [
            # element.find("b", {"class":"uDuvJd"}),
            element.find("span", {"class":"oUAcPd"}),   
            element.find("div", {"class": "RTaUke"}),   
            element.find("div", {"class": "KJ7Tg"}),    
        ]
        return any(conditions)
