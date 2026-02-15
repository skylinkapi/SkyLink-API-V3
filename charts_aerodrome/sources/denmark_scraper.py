#!/usr/bin/env python3
"""
Denmark AIM Scraper
Scrapes aerodrome charts from Denmark AIP using Selenium for SPA navigation
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import time
from contextlib import redirect_stderr
import io
import sys
import time

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


BASE_URL = "https://aim.naviair.dk"


def create_driver():
    """Create Chrome WebDriver for SPA navigation."""
    if not HAS_SELENIUM:
        raise ImportError(
            "Selenium required for Denmark. Install:\n"
            "pip install selenium webdriver-manager"
        )

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--log-level=3")  # Suppress most Chrome logging
    opts.add_argument("--disable-dev-tools")  # Disable dev tools
    opts.add_argument("--silent")  # Suppress all Chrome output
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    # Suppress Chrome stderr output during driver creation
    with redirect_stderr(io.StringIO()):
        service = Service(ChromeDriverManager().install())
        # Redirect Chrome logs to null device
        import os
        if os.name == 'nt':  # Windows
            service.log_path = 'NUL'
        else:  # Unix-like
            service.log_path = '/dev/null'
        driver = webdriver.Chrome(service=service, options=opts)

    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver


def wait_for_tree_load(driver, timeout=10):
    """Wait for the tree structure to load."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tree-grid-row"))
        )
        time.sleep(2)  # Additional wait for dynamic content
        return True
    except:
        return False


def click_tree_node(driver, node_text):
    """Click on a tree node by its text content."""
    try:
        # Find the span containing the text (using contains for partial matches)
        xpath = f"//span[contains(@class, 'ng-binding') and contains(text(), '{node_text}')]"
        elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, xpath))
        )
        
        if elements:
            # Click on the first matching element
            elements[0].click()
            time.sleep(1)  # Wait for expansion
            return True
        else:
            print(f"No elements found for '{node_text}'")
            return False
            
    except Exception as e:
        print(f"Could not click node '{node_text}': {e}")
        return False


def get_aerodrome_charts(icao_code, verbose: bool = False):
    """
    Get all aerodrome charts for a given ICAO code from Denmark AIM

    Args:
        icao_code: 4-letter ICAO code (e.g., 'EKCH')
        verbose: Enable verbose debug output

    Returns:
        List of dictionaries with 'name', 'url', and 'type' keys
    """
    charts = []
    driver = None

    try:
        if not HAS_SELENIUM:
            if verbose:
                print("Selenium not available, falling back to basic link")
            charts.append({
                'name': f'Denmark Aeronautical Information Management (AIM) - {icao_code}',
                'url': 'https://aim.naviair.dk/en/',
                'type': 'GEN'
            })
            return charts

        driver = create_driver()
        driver.get(f"{BASE_URL}/en/")
        if verbose:
            print("Loading Denmark AIM site...")

        # Wait for initial page load
        if not wait_for_tree_load(driver):
            if verbose:
                print("Tree structure did not load")
            return charts

        # Debug: Print all tree nodes found
        if verbose:
            try:
                all_nodes = driver.find_elements(By.XPATH, "//span[contains(@class, 'ng-binding')]")
                print(f"Found {len(all_nodes)} tree nodes:")
                for i, node in enumerate(all_nodes[:10]):  # Show first 10
                    print(f"  {i}: '{node.text}'")
            except Exception as e:
                print(f"Error getting tree nodes: {e}")
        
        # Navigate through the tree structure
        navigation_path = [
            "01. AIP Danmark",
            "AIP PART 3 - FLYVEPLADSER (AD)", 
            "AD 2 AERODROMES"
        ]
        
        for node_text in navigation_path:
            if verbose:
                print(f"Clicking on: {node_text}")
            if not click_tree_node(driver, node_text):
                if verbose:
                    print(f"Failed to navigate to {node_text}")
                return charts

        # Find and click on the specific airport
        # Look for airport entries that contain the ICAO code
        airport_found = False
        try:
            # Find all tree nodes that might be airports (containing ICAO)
            airport_nodes = driver.find_elements(By.XPATH, f"//span[contains(@class, 'ng-binding') and contains(text(), '{icao_code}')]")
            if airport_nodes:
                # Filter to find the one that looks like an airport name
                for node in airport_nodes:
                    text = node.text
                    if f" - {icao_code}" in text and len(text.split()) > 2:  # Should have airport name + ICAO
                        node.click()
                        time.sleep(2)
                        airport_found = True
                        break
                        
                if not airport_found:
                    # Try clicking the first one that contains the ICAO
                    airport_nodes[0].click()
                    time.sleep(2)
                    airport_found = True
            else:
                if verbose:
                    print(f"Airport {icao_code} not found in the tree")
                return charts
        except Exception as e:
            if verbose:
                print(f"Error finding airport {icao_code}: {e}")
            return charts

        if airport_found:
            # Extract PDF links from the expanded airport section
            if verbose:
                print("Extracting PDF links...")

            # Find all PDF links in the current page
            pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
            seen_urls = set()  # Track URLs to avoid duplicates

            for link in pdf_links:
                try:
                    href = link.get_attribute('href')
                    if href and '.pdf' in href.lower():
                        # Build full URL
                        full_url = urljoin(driver.current_url, href)

                        # Skip if we've already processed this URL
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        # Get the link text as chart name
                        link_text = link.text.strip()
                        if not link_text:
                            # Try to get from parent elements or nearby text
                            try:
                                parent = link.find_element(By.XPATH, "..")
                                link_text = parent.text.strip()
                            except:
                                pass

                        if not link_text or link_text.startswith('Chart '):
                            # Try to find a better name from preceding text
                            try:
                                # Look for text in the same table row or nearby
                                container = link.find_element(By.XPATH, "ancestor::tr[1] | ancestor::div[1] | ancestor::li[1]")
                                all_text = container.text.strip()
                                # Extract meaningful text, avoiding generic chart labels
                                lines = [line.strip() for line in all_text.split('\n') if line.strip() and not line.strip().startswith('Chart ')]
                                if lines:
                                    link_text = lines[0]
                            except:
                                pass

                        if not link_text:
                            link_text = f"EKCH Chart {len(charts) + 1}"

                        # URL encode the PDF filename
                        url_parts = full_url.rsplit('/', 1)
                        if len(url_parts) == 2:
                            base_url_part, filename = url_parts
                            encoded_filename = quote(filename, safe='')
                            full_url = f"{base_url_part}/{encoded_filename}"

                        # Categorize the chart
                        # Let the main CLI categorize_chart function handle this
                        # Don't set type here, let main function determine from name

                        charts.append({
                            'name': link_text,
                            'url': full_url
                        })

                except Exception as e:
                    print(f"Error processing PDF link: {e}")
                    continue

        if not charts:
            print("No PDF charts found for this airport")
            # Fallback to main site link
            charts.append({
                'name': f'Denmark Aeronautical Information Management (AIM) - {icao_code}',
                'url': 'https://aim.naviair.dk/en/',
                'type': 'GEN'
            })

    except Exception as e:
        print(f"Error scraping Denmark charts for {icao_code}: {e}")
        # Fallback
        charts.append({
            'name': f'Denmark Aeronautical Information Management (AIM) - {icao_code}',
            'url': 'https://aim.naviair.dk/en/',
            'type': 'GEN'
        })

    finally:
        if driver:
            driver.quit()

    return charts


def categorize_chart(chart_name):
    """Categorize chart based on its name"""
    chart_name_upper = chart_name.upper()

    if 'SID' in chart_name_upper or 'DEPARTURE' in chart_name_upper:
        return 'SID'
    elif 'STAR' in chart_name_upper or 'ARRIVAL' in chart_name_upper:
        return 'STAR'
    elif 'APPROACH' in chart_name_upper or 'ILS' in chart_name_upper or 'LOC' in chart_name_upper \
            or 'NDB' in chart_name_upper or 'RNP' in chart_name_upper or 'GLS' in chart_name_upper:
        return 'APP'
    elif 'AERODROME' in chart_name_upper or 'GROUND' in chart_name_upper or 'PARKING' in chart_name_upper \
            or 'TAXI' in chart_name_upper or 'MOVEMENT' in chart_name_upper:
        return 'GND'
    else:
        return 'GEN'


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python denmark_scraper.py <ICAO>")
        sys.exit(1)

    icao_code = sys.argv[1].upper()
    charts = get_aerodrome_charts(icao_code)

    if charts:
        print(f"\nFound {len(charts)} charts:")
        for chart in charts:
            print(f"  [{chart['type']}] {chart['name']}")
            print(f"    {chart['url']}")
    else:
        print("No charts found")