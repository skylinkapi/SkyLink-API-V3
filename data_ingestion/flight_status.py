
import urllib3
from bs4 import BeautifulSoup
import re

import os
from dotenv import load_dotenv


load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

def parse_flight_number(flight_number: str):
    # Normalize input: remove non-alphanumeric, lower-case
    if not flight_number:
        return flight_number
    s = re.sub(r"[^A-Za-z0-9]", "", flight_number).lower()
    # If too short to contain an IATA (2 chars) and a number, return original normalized
    if len(s) < 3:
        return s
    # Take first two characters as IATA code (per requirement) and the rest as flight number
    iata = s[:2]
    num = s[2:]
    # If the remaining part is numeric, return formatted iata-number
    if num.isdigit():
        return f"{iata}-{num}"
    # Fallback: try previous behavior (letters followed by digits)
    match = re.match(r"([a-zA-Z]+)(\d+)", flight_number)
    if match:
        return f"{match.group(1).lower()}-{match.group(2)}"
    # As last resort, return normalized string
    return s

def get_flight_status_avionio(flight_number: str):
    flight_code = parse_flight_number(flight_number)
    url = f"https://www.avionio.com/en/flight/{flight_code}"
    
    # Create HTTP pool manager with proper headers and timeout
    http = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=10.0, read=30.0),
        retries=urllib3.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        response = http.request('GET', url, headers=headers)
        if response.status != 200:
            return {"error": f"HTTP {response.status}: Flight not found or site unavailable."}
        html = response.data.decode('utf-8')
        soup = BeautifulSoup(html, "html.parser")
    except urllib3.exceptions.MaxRetryError as e:
        return {"error": f"Connection failed: {str(e.reason)}"}
    except urllib3.exceptions.ProtocolError as e:
        return {"error": f"Protocol error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    result = {}
    try:
        flight_div = soup.find('div', id='flight')
        if not flight_div:
            return {"error": "Flight information not found."}

        # Flight number
        flight_num = flight_div.find('h2', class_='h3 no-margin')
        result['flight_number'] = flight_num.text.strip() if flight_num else flight_code

        # Status - look for any paragraph with 'sc sbg' classes
        status_p = flight_div.find('p', class_=lambda x: x and 'sc' in x and 'sbg' in x)
        result['status'] = status_p.text.strip() if status_p else "Unknown"

        # Airline
        airline = "Unknown"
        first_card = flight_div.find('div', class_='card card-section')
        if first_card:
            airline_p = first_card.find_all('p')
            if len(airline_p) > 0:
                airline = airline_p[-1].text.strip()
        result['airline'] = airline

        # Departure and Arrival details
        details = flight_div.find_all('div', class_='card details')
        departure, arrival = {}, {}
        if len(details) >= 1:
            dep = details[0]
            dep_header = dep.find('div', class_='card-section card-header')
            dep_airport = dep_header.find('h2', class_='h1').text.strip() if dep_header else ""
            dep_airport_full = dep_header.find_all('p')[-1].text.strip() if dep_header else ""
            dep_body = dep.find('div', class_='card-body')
            dep_sched, dep_actual = None, None
            card_sections = dep_body.find_all('div', class_='card-section') if dep_body else []
            if len(card_sections) > 0:
                dep_sched = card_sections[0]
            if len(card_sections) > 1:
                dep_actual = card_sections[1]
            dep_sched_time = dep_sched.find('p', class_='h1 no-margin').text.strip() if dep_sched else ""
            dep_sched_date = dep_sched.find_all('p')[-1].text.strip() if dep_sched else ""
            dep_actual_time = dep_actual.find('p', class_='h1 no-margin').text.strip() if dep_actual else ""
            dep_actual_date = dep_actual.find_all('p')[-1].text.strip() if dep_actual else ""
            dep_footer = dep.find('div', class_='card-section card-footer')
            dep_footer_divs = dep_footer.find_all('div') if dep_footer else []
            dep_terminal = dep_footer_divs[0].find('p', class_='h1 no-margin').text.strip() if len(dep_footer_divs) > 0 else ""
            dep_gate = dep_footer_divs[1].find('p', class_='h1 no-margin').text.strip() if len(dep_footer_divs) > 1 else ""
            dep_checkin = dep_footer_divs[2].find('p', class_='h1 no-margin').text.strip() if len(dep_footer_divs) > 2 else ""
            departure = {
                "airport": dep_airport,
                "airport_full": dep_airport_full,
                "scheduled_time": dep_sched_time,
                "scheduled_date": dep_sched_date,
                "actual_time": dep_actual_time,
                "actual_date": dep_actual_date,
                "terminal": dep_terminal,
                "gate": dep_gate,
                "checkin": dep_checkin
            }
        if len(details) >= 2:
            arr = details[1]
            arr_header = arr.find('div', class_='card-section card-header')
            arr_airport = arr_header.find('h2', class_='h1').text.strip() if arr_header else ""
            arr_airport_full = arr_header.find_all('p')[-1].text.strip() if arr_header else ""
            arr_body = arr.find('div', class_='card-body')
            arr_sched, arr_estimated = None, None
            card_sections = arr_body.find_all('div', class_='card-section') if arr_body else []
            if len(card_sections) > 0:
                arr_sched = card_sections[0]
            if len(card_sections) > 1:
                arr_estimated = card_sections[1]
            arr_sched_time = arr_sched.find('p', class_='h1 no-margin').text.strip() if arr_sched else ""
            arr_sched_date = arr_sched.find_all('p')[-1].text.strip() if arr_sched else ""
            arr_estimated_time = arr_estimated.find('p', class_='h1 no-margin').text.strip() if arr_estimated else ""
            arr_estimated_date = arr_estimated.find_all('p')[-1].text.strip() if arr_estimated else ""
            arr_footer = arr.find('div', class_='card-section card-footer')
            arr_footer_divs = arr_footer.find_all('div') if arr_footer else []
            arr_terminal = arr_footer_divs[0].find('p', class_='h1 no-margin').text.strip() if len(arr_footer_divs) > 0 else ""
            arr_gate = arr_footer_divs[1].find('p', class_='h1 no-margin').text.strip() if len(arr_footer_divs) > 1 else ""
            arr_baggage = arr_footer_divs[2].find('p', class_='h1 no-margin').text.strip() if len(arr_footer_divs) > 2 else ""
            arrival = {
                "airport": arr_airport,
                "airport_full": arr_airport_full,
                "scheduled_time": arr_sched_time,
                "scheduled_date": arr_sched_date,
                "estimated_time": arr_estimated_time,
                "estimated_date": arr_estimated_date,
                "terminal": arr_terminal,
                "gate": arr_gate,
                "baggage": arr_baggage
            }
        result['departure'] = departure
        result['arrival'] = arrival
    except Exception as e:
        result = {"error": str(e)}
    return result