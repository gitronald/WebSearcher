import time
import json
from typing import Dict, Optional, Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .. import utils
from ..models.configs import SeleniumConfig


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
        self.user_agent = None
        self.response_code = None
        self.browser_info = {}
        
    def init_driver(self) -> None:
        """Initialize Chrome driver with selenium-specific config"""
        self.log.debug(f'SERP | init uc chromedriver | kwargs: {self.config.__dict__}')
        self.driver = uc.Chrome(**self.config.__dict__)
        self.user_agent = self.driver.execute_script('return navigator.userAgent')
        self.response_code = None
        
        # Log version information
        self.browser_info = {
            'browser_id': "",
            'browser_name': self.driver.capabilities['browserName'],
            'browser_version': self.driver.capabilities['browserVersion'],
            'driver_version': self.driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0],
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
        
    def send_request(self, url: str) -> Dict[str, Any]:
        """Use a prepared URL to conduct a search
        
        Args:
            url (str): The URL to request
            
        Returns:
            Dict[str, Any]: Dictionary containing response data
        """
        time.sleep(2)
        self.driver.get(url)
        time.sleep(2)
        
        # wait for the page to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "search")) 
        )
        time.sleep(2) #including a sleep to allow the page to fully load

        html = self.driver.page_source
        selenium_url = self.driver.current_url
        self.response_code = 0
        
        return {
            'html': html,
            'url': selenium_url,
            'response_code': self.response_code,
        }
        
    def expand_ai_overview(self):
        """Expand AI overview box by clicking it
        
        Returns:
            str: Updated HTML if expansion occurred, None otherwise
        """
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
                # Try a more thorough cleanup
                try:
                    self.driver.delete_all_cookies()
                except Exception:
                    pass
                
                try:
                    # Close all tabs/windows
                    original_handle = self.driver.current_window_handle
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                except Exception:
                    pass
                
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
