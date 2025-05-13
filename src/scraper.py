from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException, 
                                      TimeoutException, 
                                      StaleElementReferenceException)
import json
import csv
import time
import random
from .utils import load_config, get_random_user_agent, random_delay, ensure_dir_exists

class AirbnbScraper:
    def __init__(self):
        self.config = load_config()
        self.driver = self._init_driver()
        self.current_page = 1
        
    def _init_driver(self):
        options = self._get_browser_options()
        if self.config['browser'].lower() == 'chrome':
            return webdriver.Chrome(options=options)
        elif self.config['browser'].lower() == 'firefox':
            return webdriver.Firefox(options=options)
        else:
            raise ValueError("Unsupported browser specified in config")

    def _get_browser_options(self):
        user_agent = get_random_user_agent()
        
        if self.config['browser'].lower() == 'chrome':
            from selenium.webdriver.chrome.options import Options
            options = Options()
            if self.config['headless']:
                options.add_argument('--headless')
            options.add_argument(f'user-agent={user_agent}')
            options.add_argument('--disable-blink-features=AutomationControlled')
            return options
            
        elif self.config['browser'].lower() == 'firefox':
            from selenium.webdriver.firefox.options import Options
            options = Options()
            if self.config['headless']:
                options.add_argument('--headless')
            options.set_preference('general.useragent.override', user_agent)
            return options

    def scrape(self):
        try:
            print("Starting scraper...")
            self._navigate_to_search_page()
            listings = []
            
            while self.current_page <= self.config['max_pages']:
                print(f"Scraping page {self.current_page}")
                self._wait_for_listings()
                
                page_listings = self._extract_listings()
                listings.extend(page_listings)
                
                if not self._go_to_next_page():
                    break
                
                self.current_page += 1
                random_delay(
                    self.config['request_delay']['min'],
                    self.config['request_delay']['max']
                )
            
            self._save_data(listings)
            
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            self.driver.quit()

    def _navigate_to_search_page(self):
        base_url = "https://www.airbnb.com/s/homes"
        params = {
            'query': self.config['search']['location'],
            'adults': self.config['search']['adults']
        }
        
        # Add dates if specified
        if self.config['search']['checkin']:
            params['checkin'] = self.config['search']['checkin']
        if self.config['search']['checkout']:
            params['checkout'] = self.config['search']['checkout']
        
        # Build URL
        query_string = '&'.join(f"{k}={v}" for k, v in params.items() if v)
        url = f"{base_url}?{query_string}"
        
        print(f"Navigating to: {url}")  # Debug print
        self.driver.get(url)
        
        # Wait for either listings or the "Accept cookies" button
        try:
            WebDriverWait(self.driver, self.config['timeout']).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, '[itemprop="itemListElement"]') or 
                        d.find_elements(By.XPATH, "//button[contains(text(), 'Accept')]")
            )
            
            # Handle cookies if present
            try:
                cookie_accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                cookie_accept.click()
                print("Accepted cookies")
            except:
                pass
                
        except TimeoutException:
            print("Timed out waiting for page to load")
            self.driver.save_screenshot('search_page_timeout.png')

    def _wait_for_listings(self):
        try:
            WebDriverWait(self.driver, self.config['timeout']).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[itemprop="itemListElement"]'))
            )
        except TimeoutException:
            print("Timed out waiting for listings to load")

    def _extract_listings(self):
        listings = []
        listing_elements = self.driver.find_elements(By.CSS_SELECTOR, '[itemprop="itemListElement"]')
        
        for element in listing_elements:
            try:
                # Get the link first to use as a base URL
                raw_link = self._get_element_attribute(element, By.CSS_SELECTOR, 'a', 'href')
                link = f"https://www.airbnb.com{raw_link}" if raw_link else "N/A"
                
                listing = {
                    'title': self._get_element_text(element, By.CSS_SELECTOR, 'div[data-testid="listing-card-title"]'),
                    'price': self._get_element_text(element, By.CSS_SELECTOR, 'span._1y74zjx, ._tyxjp1'),  # Multiple possible classes
                    'rating': self._get_element_text(element, By.XPATH, './/span[contains(@aria-label, "out of 5 stars")]'),
                    'type': self._get_element_text(element, By.CSS_SELECTOR, 'div.f15liw5s, .t1a9j9y7'),  # Multiple possible classes
                    'beds': self._get_element_text(element, By.XPATH, './/span[contains(text(), "bed") or contains(text(), "beds")]'),
                    'location': self._get_element_text(element, By.CSS_SELECTOR, 'div.t1jojoys, .t6mzqp7'),  # Multiple possible classes
                    'link': link
                }
                
                listings.append(listing)
                
            except StaleElementReferenceException:
                print("Element became stale, skipping")
                continue
            except Exception as e:
                print(f"Error extracting listing: {e}")
                continue
                
        return listings

    def _get_element_text(self, parent, by, selector):
        try:
            element = parent.find_element(by, selector)
            return element.text.strip()
        except NoSuchElementException:
            return "N/A"

    def _get_element_attribute(self, parent, by, selector, attribute):
        try:
            element = parent.find_element(by, selector)
            return element.get_attribute(attribute)
        except NoSuchElementException:
            return "N/A"

    def _go_to_next_page(self):
        try:
            next_button = WebDriverWait(self.driver, self.config['timeout']).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Next']"))
            )
            next_button.click()
            return True
        except (NoSuchElementException, TimeoutException):
            print("No more pages available")
            return False

    def _save_data(self, listings):
        ensure_dir_exists(self.config['output_dir'])
        
        if 'csv' in self.config['output_formats']:
            csv_path = f"{self.config['output_dir']}/listings.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=listings[0].keys())
                writer.writeheader()
                writer.writerows(listings)
            print(f"Data saved to {csv_path}")
            
