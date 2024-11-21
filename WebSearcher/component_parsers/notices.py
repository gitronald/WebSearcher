import re
import copy
from ..webutils import get_text


def parse_notices(cmpt) -> list:
    notice_parser = NoticeParser()
    return notice_parser.parse_notices(cmpt)


class NoticeParser:
    def __init__(self):
        self.parsed = {}
        self.sub_type = "unknown"
        self.sub_type_text = {
            "query_edit": {"Showing results for", "Including results for"},
            "query_edit_no_results": {"No results found for"},
            "query_suggestion": {
                "Did you mean:", 
                "Are you looking for:", 
                "Search for this instead?", 
                "Did you mean to search for:", 
                "Search instead for:"
            },
            "location_choose_area": {"Results for", "Choose area"},
            "location_use_precise_location": {"Results for", "Use precise location"},
            "language_tip": {"Tip:", "Learn more about filtering by language"}
        }
        self.parser_dict = {
            'query_edit': self._parse_query_edit,
            'query_edit_no_results': self._parse_no_results_replacement,
            'query_suggestion': self._parse_query_suggestion,
            'location_choose_area': self._parse_location_choose_area,
            'location_use_precise_location': self._parse_location_use_precise_location,
            'language_tip': self._parse_language_tip
        }

    def parse_notices(self, cmpt) -> list:
        """Parse a query notices component"""

        self._classify_sub_type(cmpt)
        self._parse_sub_type(cmpt)
        self._package_parsed()
        return self.parsed_list

    def _classify_sub_type(self, cmpt) -> str:
        """Classify the sub-type of a query notice component"""
        cmpt_text = cmpt.text.strip()
        cmpt_text = re.sub(r'\s+', ' ', cmpt_text)

        for sub_type, text_list in self.sub_type_text.items():
            if sub_type.startswith("location_"):
                if all(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break
            elif sub_type.startswith("query_"):
                if any(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break
            elif sub_type.startswith("language_"):
                if all(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break

    def _parse_sub_type(self, cmpt):
        sub_parser = self.parser_dict.get(self.sub_type, None)
        if sub_parser:
            self.parsed = sub_parser(cmpt)

    def _package_parsed(self):
        self.parsed_list = [{
            'type': 'notice',
            'sub_type': self.sub_type,
            'sub_rank': 0,
            'title': self.parsed.get('title', None),
            'text': self.parsed.get('text', None)
        }]

    def _parse_no_results_replacement(self, cmpt) -> dict:
        output = {"title": None, "text": None}

        cmpt = copy.copy(cmpt)
        div_title = cmpt.find('div', {'role':'heading', 'aria-level': '2'})
        if div_title:
            output['title'] = div_title.text.strip()
            div_title.extract()

        div_text = cmpt.find("div", {"class": "card-section"})
        if div_text:
            output['text'] = div_text.text.strip()

        return output

    def _parse_query_edit(self, cmpt) -> dict:
        output = {"title": None, "text": None}
        showing_results_span = cmpt.find('span', class_='gL9Hy')
        if showing_results_span:
            output['title'] = showing_results_span.text.strip()

        modified_query_link = cmpt.find('a', id='fprsl')
        if modified_query_link:
            modified_query = modified_query_link.text.strip()
            output['title'] += f" {modified_query}"

        search_instead_span = cmpt.find('span', class_='spell_orig')
        if search_instead_span:
            output['text'] = search_instead_span.text.strip()

        original_query_link = cmpt.find('a', class_='spell_orig')
        if original_query_link:
            original_query = original_query_link.text.strip()
            output['text'] += f" {original_query}"
        return output

    def _parse_query_suggestion(self, cmpt) -> dict:
        output = {"title": None, "text": None}

        # check in div and span with same class
        cmpt_checks = {
            cmpt.find('span', class_='gL9Hy'),
            cmpt.find('div', class_='gL9Hy')
        }
        for cmpt_check in cmpt_checks:
            if cmpt_check:
                output['title'] = cmpt_check.text.strip()
                break

        suggestion_links = cmpt.find_all('a', class_='gL9Hy')
        suggested_queries = [get_text(suggestion_link) for suggestion_link in suggestion_links if suggestion_link]
        output['text'] = '<|>'.join(suggested_queries)

        return output

    def _parse_location_choose_area(self, cmpt) -> dict:
        output = {"title": None, "text": None}
        
        # Extract the main heading
        heading = cmpt.find('div', class_='eKPi4')
        if heading:
            results_for_span = heading.find('span', class_='gm7Ysb')
            location_span = heading.find('span', class_='BBwThe')
            
            if results_for_span and location_span:
                output['title'] = f"{results_for_span.text.strip()} {location_span.text.strip()}"
        
        return output

    def _parse_location_use_precise_location(self, cmpt) -> dict:
        output = {"title": None, "text": None}
        
        # Extract the main heading
        heading = cmpt.find('div', class_='eKPi4')
        if heading:
            results_for_span = heading.find('span', class_='gm7Ysb')
            location_span = heading.find('span', class_='BBwThe')
            
            if results_for_span and location_span:
                output['title'] = f"{results_for_span.text.strip()} {location_span.text.strip()}"
        
        return output

    def _parse_language_tip(self, cmpt) -> dict:
        output = {"title": None, "text": None}   
        title_div = cmpt.find('div', class_='Ww4FFb')
        if title_div:
            output['title'] = re.sub(r'\s+', ' ', title_div.text)

        return output

