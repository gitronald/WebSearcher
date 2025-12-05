import bs4
from .. import webutils
from ..logger import Logger

log = Logger().start(__name__)

class ExtractorMain:
    def __init__(self, soup: bs4.BeautifulSoup, components):
        self.soup = soup
        self.components = components

        # copied from Extractor.__init__
        self.layout_divs = {
            "rso": None,
            "top-bars": None,
            "left-bar": None,
        }
        self.layouts = {
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

    def extract(self):
        self.get_layout()
        self._ads_top()
        self._main_column()
        self._ads_bottom()
        log.debug(f"main_components: {self.components.cmpt_rank_counter:,}")

    def get_layout(self):
        """Divide and label the page layout"""

        # Layout soup subsets
        layout_divs = {}
        layout_divs['rso'] = self.soup.find('div', {'id':'rso'})
        layout_divs['left-bar'] = self.soup.find('div', {'class': 'OeVqAd'})
        
        rcnt = self.soup.find('div', {'id':'rcnt'})
        layout_divs['top-bars'] = webutils.find_all_divs(rcnt, 'div', {'class': ['XqFnDf', 'M8OgIe']})
        
        # Layout classifications
        layouts = {}
        layouts['top-bars'] = bool(layout_divs['top-bars'])
        layouts['left-bar'] = bool(layout_divs['left-bar'])
        layouts['standard'] = (
            bool(layout_divs['rso']) &
            (not layouts['top-bars']) &
            (not layouts['left-bar'])
        )
        layouts['no-rso'] = not bool(layout_divs['rso'])

        if layouts['top-bars'] and bool(layout_divs['rso']) and not layouts['left-bar']:
            layout_label = 'standard'
        else:    
            # Get layout label
            label_matches = [k for k,v in layouts.items() if v]
            layout_label = label_matches[0] if label_matches else None

        # Set layout details
        log.debug(f"main_layout: {layout_label}")
        self.layout_label = layout_label
        self.layouts.update(layouts)
        self.layout_divs.update(layout_divs)

    def _ads_top(self):
        ads = self.soup.find('div', {'id':'tads'})
        if ads and webutils.get_text(ads):
            ads.extract()
            self.components.add_component(ads, section='main', type='ad')

    def _main_column(self, drop_tags: set = {'script', 'style', None}):
        try:
            extractor = self.layout_extractors[self.layout_label]
        except KeyError:
            raise ValueError(f"no extractor for layout_label: {self.layout_label}")

        column = extractor(drop_tags)
        column = webutils.filter_empty_divs(column)
        for c in column:
            if ExtractorMain.is_valid(c):
                self.components.add_component(c, section='main')

    def _ads_bottom(self):
        ads = self.soup.find('div', {'id':'tadsb'})
        if ads and webutils.get_text(ads):
            ads.extract()
            self.components.add_component(ads, section='main', type='ad')

    def extract_from_standard(self, drop_tags:set={}) -> list:

        rso_div = self.layout_divs['rso']
        standard_layouts = {
            "standard-0": rso_div.find('div', {'id':'kp-wp-tab-overview'}),
            "standard-1": rso_div.find('div', {'id':'kp-wp-tab-cont-Songs', 'role':'tabpanel'}),
            "standard-2": rso_div.find('div', {'id':'kp-wp-tab-SportsStandings'}),
        }
        for layout_name, layout_div in standard_layouts.items():
            if layout_div:
                if layout_div.find_all("div"):
                    return self._extract_from_standard_sub_type(layout_name)

        top_divs = ExtractorMain.extract_top_divs(self.layout_divs['top-bars']) or []
        col = ExtractorMain.extract_children(rso_div, drop_tags)
        col = top_divs + col
        col = [c for c in col if ExtractorMain.is_valid(c)]
        if not col:
            self.layout_label = 'standard-3'
            log.debug(f"main_layout: {self.layout_label} (update)")
            divs = rso_div.find_all('div', {'id':'kp-wp-tab-overview'})
            col = sum([d.find_all('div', {'class':'TzHB6b'}) for d in divs], [])
        return col

    def _extract_from_standard_sub_type(self, sub_type:str = "") -> list:
        
        self.layout_label = sub_type
        rso_div = self.layout_divs['rso']
        log.debug(f"main_layout: {self.layout_label} (update)")
        
        if self.layout_label == "standard-0":
            column = []
            top_divs = ExtractorMain.extract_top_divs(self.layout_divs['top-bars']) or []
            main_divs = rso_div.find_all('div', {'class':'TzHB6b'}) or []
            column.extend(top_divs)
            column.extend(main_divs)
            log.debug(f"main_components: {len(column):,}")
            return column
    
        if self.layout_label == "standard-1":
            column = []
            top_divs = ExtractorMain.extract_top_divs(self.layout_divs['top-bars']) or []
            main_divs = rso_div.find('div', {'id':'kp-wp-tab-Songs'}).children or []
            column.extend(top_divs)
            column.extend(main_divs)
            column = [div for div in column if div.name not in {'script', 'style'}]
            column = webutils.filter_empty_divs(column)
            return column
        
        if self.layout_label == "standard-2":
            column = []
            top_divs = ExtractorMain.extract_top_divs(self.layout_divs['top-bars']) or []
            main_divs = rso_div.find('div', {'id':'kp-wp-tab-SportsStandings'}).children or []
            column.extend(top_divs)
            column.extend(main_divs)
            column = [div for div in column if div.name not in {'script', 'style'}]
            column = webutils.filter_empty_divs(column)
            return column
            

    def extract_from_top_bar(self, drop_tags:set={}) -> list:
        out = []
        tops = ExtractorMain.extract_top_divs(self.layout_divs['top-bars'])
        out.extend(tops)

        div_classes = [
            'cUnQKe', # people also ask
            'g',      # general
            'Lv2Cle', # images-medium
            'oIk2Cb', # searches_related
            'Ww4FFb', # discussions_and_forums
            'vtSz8d', # videos
            'uVMCKf', # videos
        ]

        rso_divs = self.layout_divs['rso'].find_all('div', attrs={'class':div_classes})
        if rso_divs:
            self.layout_label = 'top-bars-divs'
            col = [div for div in rso_divs if div.name not in drop_tags]
        else:
            self.layout_label = 'top-bars-children'
            col = ExtractorMain.extract_children(self.layout_divs['rso'], drop_tags)
        log.debug(f"main_layout: {self.layout_label} (update)")
        out.extend(col)
        return out

    @staticmethod
    def extract_top_divs(soup, drop_tags:set={}) -> list:
        out = []
        for tb in soup:
            if webutils.check_dict_value(tb.attrs, "class", ["M8OgIe"]):
                kd = webutils.find_all_divs(tb, "div", {"jscontroller":["qTdDb","OWrb3e"]})
                out.extend(kd)
            else:
                out.append(tb)
        return out

    def extract_from_left_bar(self, drop_tags:set={}) -> list:
        return self.soup.find_all('div', {'class':'TzHB6b'})

    def extract_from_no_rso(self, drop_tags:set={}) -> list:
        out=[]; sec1=self.soup.find_all('div', {'class':'UDZeY OTFaAf'})
        for div in sec1:
            if div.find('h2') and div.find('h2').text=="Twitter Results":
                out.append(div.find('div').parent)
            elif div.find('g-section-with-header'):
                out.append(div.find('g-section-with-header').parent)
            elif div.find('g-more-link'):
                out.append(div)
            elif div.find('div',{'class':'oIk2Cb'}):
                out.append(div)
            else:
                out.extend(div.find_all('div',{'class':'g'}))
            sec2=self.soup.find('div',{'class':'WvKfwe a3spGf'})
            if sec2:
                out.extend(sec2.children)
        return [c for c in out if c.name not in drop_tags]

    @staticmethod
    def extract_children(soup, drop_tags:set={}) -> list:
        cts=[]
        for ch in soup.children:
            if ch.name in drop_tags: continue
            if not ch.attrs: cts.extend(ch.contents)
            else: cts.append(ch)
        return cts

    @staticmethod
    def is_valid(c) -> bool:
        if not c: return False
        bad = {"Main results","Twitter Results",""}
        if c.text in bad: return False
        # hidden survey
        cond = [
            c.find('promo-throttler'),
            webutils.check_dict_value(c.attrs,"class",["ULSxyf"]) if 'attrs' in c else False,
        ]
        if all(cond): return False
        return True