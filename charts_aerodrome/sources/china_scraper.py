"""
China eAIP Scraper
Fetches aerodrome charts from China's eAIP system.
Based on https://eaip.apocfly.com/
"""

import time
import re
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class ChinaScraper:
    """Scraper for China eAIP aerodrome charts."""
    
    BASE_URL = "https://eaip.apocfly.com/"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.driver = None
    
    def _init_driver(self):
        """Initialize Selenium WebDriver."""
        if self.driver:
            return
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        if self.verbose:
            print("Initializing Chrome WebDriver...")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def __del__(self):
        """Clean up WebDriver on destruction."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for a Chinese airport.
        
        Note: This scraper uses Selenium and may be slow (30-90 seconds).
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'ZBAA', 'ZSPD')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        try:
            self._init_driver()
            
            if self.verbose:
                print(f"⚠️  Selenium automation in progress - this may take 30-90 seconds...")
                print(f"Loading {self.BASE_URL}")
            
            # Load the main page
            self.driver.get(self.BASE_URL)
            wait = WebDriverWait(self.driver, 15)
            time.sleep(5)  # Wait for Vue app to fully load
            
            if self.verbose:
                print("Expanding AD 2 AERODROMES...")
            
            # AD 2 AERODROMES is visible by default (PART 3 is expanded)
            # Use JavaScript click to bypass interactable issues with Vue/Element UI
            ad2 = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//span[@title='AD 2 AERODROMES']")
            ))
            self.driver.execute_script("arguments[0].click();", ad2)
            time.sleep(3)
            
            if self.verbose:
                print(f"Finding airport {icao_code}...")
            
            # Find and click airport using JavaScript
            airport = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//span[starts-with(@title, '{icao_code}-')]")
            ))
            self.driver.execute_script("arguments[0].click();", airport)
            time.sleep(2)
            
            if self.verbose:
                print("Opening Charts section...")
            
            # Click "Charts related to an aerodrome" using JavaScript
            charts_link = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//span[contains(@title, 'Charts related') or contains(@title, 'charts related')]")
            ))
            self.driver.execute_script("arguments[0].click();", charts_link)
            time.sleep(2)
            
            if self.verbose:
                print("Extracting chart list...")
            
            # Find all chart items in the tree (they start with ICAO code)
            chart_elements = self.driver.find_elements(
                By.XPATH,
                f"//span[starts-with(@title, '{icao_code}-') and contains(@title, ':')]"
            )
            
            if self.verbose:
                print(f"Found {len(chart_elements)} charts, extracting URLs...")
            
            charts = []
            for i, element in enumerate(chart_elements):
                try:
                    chart_title = element.get_attribute('title')
                    
                    # Click the chart to load PDF using JavaScript
                    self.driver.execute_script("arguments[0].click();", element)
                    time.sleep(1.0)  # Wait for PDF to load
                    
                    # Find iframe with PDF
                    try:
                        iframe = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.TAG_NAME, 'iframe'))
                        )
                        pdf_url = iframe.get_attribute('src')
                        
                        if pdf_url and '.pdf' in pdf_url:
                            chart_name = self._parse_chart_name(chart_title)
                            chart_type = self._categorize_chart(chart_name, chart_title)
                            
                            charts.append({
                                'name': chart_name,
                                'url': pdf_url,
                                'type': chart_type
                            })
                            
                            if self.verbose:
                                print(f"  [{i+1}/{len(chart_elements)}] {chart_name}")
                    except TimeoutException:
                        if self.verbose:
                            print(f"  [{i+1}/{len(chart_elements)}] ⚠️  No PDF found for {chart_title}")
                
                except Exception as e:
                    if self.verbose:
                        print(f"  Error: {e}")
                    continue
            
            return charts
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
            return []
    
    def _parse_chart_name(self, title: str) -> str:
        """Parse chart name from title like 'ZBAA-2P-1:APDC RWY01/36L/36R'."""
        if ':' in title:
            # Format: "ZBAA-2P-1:APDC RWY01/36L/36R"
            parts = title.split(':', 1)
            if len(parts) == 2:
                return parts[1].strip()
        
        # Fallback: remove ICAO prefix
        if '-' in title:
            parts = title.split('-', 1)
            if len(parts) == 2:
                return parts[1].strip()
        
        return title
    
    def _categorize_chart(self, name: str, title: str) -> str:
        """
        Categorize a chart based on its name and title.
        
        Args:
            name: Parsed chart name
            title: Full chart title
            
        Returns:
            Chart type: 'general', 'airport_diagram', 'sid', 'star', or 'approach'
        """
        name_lower = name.lower()
        title_lower = title.lower()
        combined = f"{name_lower} {title_lower}"
        
        # Check title codes: 2P/2R = parking/runway (ground), 3P = SID, 2R = STAR, etc.
        if '-3p-' in title_lower or 'sid' in combined:
            return 'sid'
        
        if '-3r-' in title_lower or 'star' in combined:
            return 'star'
        
        if '-3' in title_lower and 'approach' in combined:
            return 'approach'
        
        if any(keyword in combined for keyword in [
            'approach', 'app', 'iac', 'ils', 'vor', 'ndb', 'rnav', 'rnp',
            'landing', 'final'
        ]):
            return 'approach'
        
        if any(keyword in combined for keyword in [
            'apdc', 'parking', 'ground', 'taxi', 'adc', 'aerodrome chart',
            '-2p-', '-2r-', '-0g-', 'movement'
        ]):
            return 'airport_diagram'
        
        return 'general'


if __name__ == '__main__':
    # Test the scraper
    import sys
    
    icao = sys.argv[1] if len(sys.argv) > 1 else 'ZBAA'  # Beijing Capital
    
    scraper = ChinaScraper(verbose=True)
    charts = scraper.get_charts(icao)
    
    print(f"\nFound {len(charts)} charts:")
    for chart in charts:
        print(f"  {chart['type']}: {chart['name']}")
        print(f"    {chart['url']}")
