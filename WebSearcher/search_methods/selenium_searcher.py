import time
import json
from typing import Dict, Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .. import utils
from ..models.configs import SeleniumConfig
from ..models.searches import SearchParams

class SeleniumDriver:
    """Handle Selenium-based web interactions for search engines"""
    
    def __init__(self, config: SeleniumConfig, logger):
        """Initialize a Selenium driver with the given configuration
        
        Args:
            config (SeleniumConfig): Configuration for Selenium
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.driver = None
        self.browser_info = {}
        
    def init_driver(self) -> None:
        """Initialize Chrome driver with selenium-specific config"""
        self.log.debug(f'SERP | init uc chromedriver | kwargs: {self.config.__dict__}')
        self.driver = uc.Chrome(**self.config.__dict__)
        
        # Log version information
        self.browser_info = {
            'browser_id': "",
            'browser_name': self.driver.capabilities['browserName'],
            'browser_version': self.driver.capabilities['browserVersion'],
            'driver_version': self.driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0],
            'user_agent': self.driver.execute_script('return navigator.userAgent'),
        }
        self.browser_info['browser_id'] = utils.hash_id(json.dumps(self.browser_info))
        self.log.debug(json.dumps(self.browser_info, indent=4))
        
    def send_typed_query(self, query: str):
        """Send a typed query to the search box"""
        time.sleep(2)
        self.driver.get('https://www.google.com')
        time.sleep(2)
        search_box = self.driver.find_element(By.ID, "APjFqb")
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        
    def send_request(self, search_params: SearchParams, ai_expand: bool = False) -> Dict[str, Any]:
        """Visit a URL with selenium and save HTML response"""

        response_output = {
            'html': '',
            'url': search_params.url,
            'user_agent': self.browser_info['user_agent'],
            'response_code': 0,
        }

        try:
            self.driver.get(search_params.url)
            time.sleep(2)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "search")) 
            )
            time.sleep(2)
            response_output['html'] = self.driver.page_source
            response_output['url'] = self.driver.current_url
            response_output['response_code'] = 200

            # Expand AI overview if requested
            if ai_expand:
                expanded_html = self.expand_ai_overview()
                if expanded_html:
                    len_diff = len(expanded_html) - len(response_output['html'])
                    self.log.debug(f"SERP | expanded html | len diff: {len_diff}")
                    response_output['html'] = expanded_html

        except Exception as e:
            self.log.exception(f'SERP | Chromedriver error | {str(e)}')
        finally:
            self.delete_cookies()
            return response_output

    def expand_ai_overview(self):
        """Expand AI overview box by clicking it"""
        show_more_button_xpath = "//div[@jsname='rPRdsc' and @role='button']"
        show_all_button_xpath = '//div[contains(@class, "trEk7e") and @role="button"]'

        try:
            self.driver.find_element(By.XPATH, show_more_button_xpath)
            show_more_button_exists = True
        except NoSuchElementException:
            show_more_button_exists = False
        
        if show_more_button_exists:
            try:
                show_more_button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.XPATH, show_more_button_xpath))
                )
                if show_more_button is not None:
                    show_more_button.click()
                    try:
                        time.sleep(2) # Wait for additional content to load
                        show_all_button = WebDriverWait(self.driver, 1).until(
                            EC.element_to_be_clickable((By.XPATH, show_all_button_xpath))
                        )
                        show_all_button.click()
                    except Exception:
                        pass
                    
                    # Return expanded content
                    return self.driver.page_source

            except Exception:
                pass
        
        return None
        
    def cleanup(self) -> bool:
        """Clean up resources, particularly Selenium's browser instance
        
        Returns:
            bool: True if cleanup was successful or not needed, False if cleanup failed
        """
        if self.driver:
            try:
                self.delete_cookies()      
                self.close_all_windows()          
                # Finally quit the driver
                self.driver.quit()
                self.driver = None
                self.log.debug(f'Browser successfully closed')
                return True
            except Exception as e:
                self.log.warning(f'Failed to close browser: {e}')
                # Force driver to be None so we create a fresh instance next time
                self.driver = None
                return False
        return True
    
    def close_all_windows(self):
        try:
            # Close all tabs/windows
            original_handle = self.driver.current_window_handle
            for handle in self.driver.window_handles:
                self.driver.switch_to.window(handle)
                self.driver.close()
            self.driver.switch_to.window(original_handle)
            self.driver.close()
        except Exception:
            pass
    
    def delete_cookies(self):
        """Delete all cookies from the browser"""
        if self.driver:
            try:
                self.driver.delete_all_cookies()
            except Exception as e:
                self.log.warning(f"Failed to delete cookies: {str(e)}")
                
    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass
