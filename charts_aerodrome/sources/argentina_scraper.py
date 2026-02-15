"""
Argentina ANAC (Administración Nacional de Aviación Civil) Scraper
Fetches aerodrome charts from Argentina's official aeronautical information system.

NOTE: This website is a JavaScript-heavy SPA (Single Page Application) that requires
browser automation (Selenium) to properly scrape. The website dynamically loads content
when you search for an ICAO code in the AD (Aerodrome) section.

Installation requirements:
    pip install selenium webdriver-manager

Dependencies:
    - Chrome browser (or ChromeDriver)
    - selenium library
    - webdriver-manager for automatic ChromeDriver management
"""

import time
import re
from typing import List, Dict

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ArgentinaScraper:
    """Scraper for Argentina ANAC aerodrome charts using Selenium."""
    
    BASE_URL = "https://ais.anac.gob.ar/aip#ad"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium is required for Argentina scraper. Install with:\n"
                "pip install selenium webdriver-manager"
            )
    
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Automatically download and setup ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def get_charts(self, icao_code: str) -> List[Dict[str, str]]:
        """
        Fetch aerodrome charts for an Argentinian airport.
        
        Args:
            icao_code: ICAO code of the airport (e.g., 'SAEZ', 'SABE')
            
        Returns:
            List of chart dictionaries with 'name', 'url', and 'type' keys
        """
        icao_code = icao_code.upper()
        
        if self.verbose:
            print(f"[DEBUG] Setting up Chrome WebDriver...")
        
        driver = None
        charts = []
        
        try:
            driver = self._setup_driver()
            
            if self.verbose:
                print(f"[DEBUG] Navigating to {self.BASE_URL}")
            
            driver.get(self.BASE_URL)
            
            # Wait for page to load
            time.sleep(3)
            
            if self.verbose:
                print(f"[DEBUG] Page loaded. Current URL: {driver.current_url}")
                print(f"[DEBUG] Page title: {driver.title}")
            
            # Click the "Ad" tab to navigate to Aerodrome section
            try:
                if self.verbose:
                    print(f"[DEBUG] Looking for AD tab to click...")
                
                # Try to find and click the AD tab using XPath (simpler approach)
                ad_tab = None
                try:
                    # Look for link with text "Ad" or href containing "#ad"
                    ad_tab = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Ad') or contains(@href, '#ad')]"))
                    )
                except:
                    if self.verbose:
                        print(f"[DEBUG] XPath method failed, trying CSS selector...")
                    try:
                        ad_tab = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='#ad']"))
                        )
                    except:
                        pass
                
                if ad_tab:
                    if self.verbose:
                        print(f"[DEBUG] Found AD tab: {ad_tab.text}")
                    ad_tab.click()
                    time.sleep(3)  # Wait for tab content to load
                    if self.verbose:
                        print(f"[DEBUG] AD tab clicked successfully")
                else:
                    if self.verbose:
                        print(f"[DEBUG] Could not find AD tab")
                    return []
                    
            except Exception as e:
                if self.verbose:
                    print(f"[DEBUG] Error clicking AD tab: {e}")
                return []
            
            # Try multiple strategies to find search input
            search_input = None
            search_selectors = [
                "input[type='search']",
                "input[placeholder*='Buscar']",
                "input[placeholder*='buscar']",
                ".search-input",
                "#search",
                "input[class*='search']"
            ]
            
            for selector in search_selectors:
                try:
                    if self.verbose:
                        print(f"[DEBUG] Trying selector: {selector}")
                    search_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if search_input:
                        break
                except:
                    continue
            
            if not search_input:
                if self.verbose:
                    print(f"[DEBUG] Could not find search input with any selector")
                    print(f"[DEBUG] Saving page source for debugging...")
                    with open("argentina_debug.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    print(f"[DEBUG] Page source saved to argentina_debug.html")
                
                # Try to find charts anyway by looking for all links
                all_links = driver.find_elements(By.TAG_NAME, "a")
                if self.verbose:
                    print(f"[DEBUG] Found {len(all_links)} total links on page")
                
                # Filter for chart-related links
                for link in all_links:
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        
                        if not href or not text:
                            continue
                        
                        # Look for ICAO code in link or text
                        if icao_code in text.upper() or icao_code in href.upper():
                            if 'descarga' in href or 'carta' in href.lower() or 'chart' in href.lower():
                                chart_type = self._categorize_chart(text)
                                charts.append({
                                    'name': text,
                                    'url': href,
                                    'type': chart_type
                                })
                    except:
                        continue
                
                return charts
            
            if self.verbose:
                print(f"[DEBUG] Found search input, entering {icao_code}...")
            
            search_input.clear()
            search_input.send_keys(icao_code)
            
            # Wait for search results
            time.sleep(3)
            
            # Save HTML after search for debugging (only if verbose and small enough)
            if self.verbose:
                page_source = driver.page_source
                if len(page_source) < 500000:  # Only if less than 500KB
                    try:
                        with open("argentina_search_result.html", "w", encoding="utf-8") as f:
                            f.write(page_source)
                        print(f"[DEBUG] Search result HTML saved to argentina_search_result.html")
                    except:
                        print(f"[DEBUG] Could not save HTML (too large or error)")
                else:
                    print(f"[DEBUG] Page source too large ({len(page_source)} bytes), skipping save")
            
            if self.verbose:
                print(f"[DEBUG] Search completed, looking for chart links...")
            
            # The charts appear in a table structure
            # Each row has a <td> with the chart name and an <a> with href containing 'descarga'
            seen_urls = set()
            
            try:
                # Find all table rows
                rows = driver.find_elements(By.CSS_SELECTOR, "tr")
                
                if self.verbose:
                    print(f"[DEBUG] Found {len(rows)} table rows")
                
                for row in rows:
                    try:
                        # Look for a cell with the chart name (contains ICAO code)
                        name_cell = row.find_element(By.CSS_SELECTOR, "td")
                        chart_name = name_cell.text.strip()
                        
                        # Skip if doesn't contain ICAO code
                        if icao_code not in chart_name:
                            continue
                        
                        # Find the download link in this row
                        download_link = row.find_element(By.CSS_SELECTOR, "a[href*='descarga']")
                        chart_url = download_link.get_attribute('href')
                        
                        if chart_url in seen_urls:
                            continue
                        
                        seen_urls.add(chart_url)
                        
                        # Categorize based on chart name
                        chart_type = self._categorize_chart(chart_name)
                        
                        charts.append({
                            'name': chart_name,
                            'url': chart_url,
                            'type': chart_type
                        })
                        
                    except:
                        continue
                
            except Exception as e:
                if self.verbose:
                    print(f"[DEBUG] Error finding table rows: {e}")
            
            # Fallback: try original link-based approach if no charts found
            if not charts:
                if self.verbose:
                    print(f"[DEBUG] No charts found in table structure, trying link-based approach...")
                
                link_selectors = [
                    f"a[href*='descarga']",
                    f"a[href*='{icao_code}']",
                    f"a[href*='carta']",
                    f"a[href*='chart']",
                    f"a[title*='{icao_code}']"
                ]
                
                for selector in link_selectors:
                    try:
                        chart_links = driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if self.verbose:
                            print(f"[DEBUG] Selector '{selector}' found {len(chart_links)} links")
                        
                        for link in chart_links:
                            try:
                                chart_name = link.text.strip()
                                chart_url = link.get_attribute('href')
                                
                                if not chart_name or not chart_url or chart_url in seen_urls:
                                    continue
                                
                                # Filter out non-chart links
                                if not any(keyword in chart_url.lower() for keyword in ['descarga', 'carta', 'chart', 'pdf']):
                                    continue
                                
                                seen_urls.add(chart_url)
                                chart_type = self._categorize_chart(chart_name)
                                
                                charts.append({
                                    'name': chart_name,
                                    'url': chart_url,
                                    'type': chart_type
                                })
                                
                            except Exception as e:
                                if self.verbose:
                                    print(f"[DEBUG] Error processing link: {e}")
                                continue
                    except:
                        continue
            
            if self.verbose:
                print(f"[DEBUG] Successfully extracted {len(charts)} charts")
            
        except Exception as e:
            print(f"Error scraping Argentina charts for {icao_code}: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
        
        finally:
            if driver:
                driver.quit()
        
        return charts
    
    def _categorize_chart(self, chart_name: str) -> str:
        """Categorize chart based on its name.
        
        Check specific AIP codes FIRST before general keywords to avoid false matches.
        """
        chart_name_lower = chart_name.lower()
        
        # PRIORITY 1: Check specific Argentina AIP codes first
        # These are explicit chart type identifiers that take precedence
        
        # SID codes
        if 'ad-2.i' in chart_name_lower:
            return 'sid'
        
        # STAR codes  
        if 'ad-2.k' in chart_name_lower:
            return 'star'
        
        # Approach codes
        if any(code in chart_name_lower for code in ['ad-2.g', 'ad-2.m']):
            return 'approach'
        
        # Ground diagram codes
        if any(code in chart_name_lower for code in ['ad-2.a', 'ad-2.b', 'ad-2.c', 'ad-2.d']):
            return 'airport_diagram'
        
        # Area charts and airport data codes (these are informational/GEN)
        if any(code in chart_name_lower for code in ['ad-2.0', 'ad-2.h']):
            return 'airport_diagram'
        
        # PRIORITY 2: Check general keywords (only if no specific code matched)
        
        # SID keywords
        if any(keyword in chart_name_lower for keyword in [
            'sid', 'salida normalizada', 'standard instrument departure',
            'departure', 'partida'
        ]):
            return 'sid'
        
        # STAR keywords
        if any(keyword in chart_name_lower for keyword in [
            'star', 'llegada normalizada', 'standard terminal arrival',
            'arrival', 'arribo', 'llegada'
        ]):
            return 'star'
        
        # Approach keywords
        if any(keyword in chart_name_lower for keyword in [
            'iac', 'aproximación por instrumentos', 'instrument approach',
            'aproximaciones de precisión', 'precision approach',
            'approach', 'aproximación', 'aproximacion',
            'ils', 'rnav', 'vor', 'ndb', 'loc', 'rnp'
        ]):
            return 'approach'
        
        # Ground/Airport diagram keywords
        if any(keyword in chart_name_lower for keyword in [
            'plano de aeródromo', 'plano de aerodromo', 'aerodrome chart',
            'plano de estacionamiento', 'parking',
            'movimientos en tierra', 'ground movement',
            'plano de obstáculos', 'obstacles',
            'atraque', 'docking', 'helipuerto', 'heliport'
        ]):
            return 'airport_diagram'
        
        # Default to airport_diagram for unclear cases
        return 'airport_diagram'
