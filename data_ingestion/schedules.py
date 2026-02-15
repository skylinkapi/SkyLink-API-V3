import httpx
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)
BASE_URL = "https://www.avionio.com/widget/en/{iata}/{direction}?style=2"

async def fetch_schedule(iata: str, direction: str = "departures"):
    """Fetch schedule data from external source"""
    try:
        url = BASE_URL.format(iata=iata, direction=direction)
        logger.info(f"Fetching schedule data for {iata} ({direction})")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            
            if resp.status_code == 404:
                logger.warning(f"Schedule not found for {iata} ({direction})")
                return {"error": "Schedule data not available for this airport"}
            
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching schedule for {iata}: {e.response.status_code}")
        return {"error": "Schedule data not available for this airport"}
    except httpx.RequestError as e:
        logger.error(f"Request error fetching schedule for {iata}: {e}")
        return {"error": "Unable to fetch schedule data at this time"}
    except Exception as e:
        logger.error(f"Unexpected error fetching schedule for {iata}: {e}")
        return {"error": "Unable to fetch schedule data at this time"}
    try:
        # The widget is a table, parse rows
        table = soup.find("table")
        if not table:
            logger.warning(f"No table found in schedule data for {iata}")
            return {"error": "No schedule data found"}
        
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not headers:
            logger.warning(f"No headers found in schedule table for {iata}")
            return {"error": "Invalid schedule data format"}
        
        flights = []
        for row in table.find_all("tr")[1:]:
            cells = []
            for i, td in enumerate(row.find_all("td")):
                # Remove all spans that might contain codeshare counts
                for span in td.find_all("span"):
                    if span.get("class") and any("count" in cls.lower() for cls in span.get("class")):
                        span.decompose()
                    elif span.get("title") and "codeshare" in span.get("title").lower():
                        span.decompose()
                    elif span.text.strip().isdigit():  # Remove spans containing only numbers
                        span.decompose()
                
                # Remove all <a> tags that might contain codeshare counts
                for a_tag in td.find_all("a"):
                    if a_tag.get("class") and any("count" in cls.lower() for cls in a_tag.get("class")):
                        a_tag.decompose()
                    elif a_tag.get("title") and "codeshare" in a_tag.get("title").lower():
                        a_tag.decompose()
                    elif a_tag.text.strip().isdigit():  # Remove <a> tags containing only numbers
                        a_tag.decompose()
                
                cell_text = td.get_text(strip=True)
                
                # Only apply trailing number removal to non-flight columns
                # Flight numbers should preserve their numeric parts (e.g., "7L276")
                # Time columns should preserve their format (e.g., "20:30")
                if i < len(headers):
                    header = headers[i].lower()
                    # Don't remove trailing numbers from flight-related, time-related, or gate columns
                    if not any(keyword in header for keyword in ['flight', 'airline', 'aircraft', 'time', 'gate', 'terminal']):
                        import re
                        cell_text = re.sub(r'\d+$', '', cell_text).strip()
                
                cells.append(cell_text)
            
            if cells and len(cells) == len(headers):
                row_dict = dict(zip(headers, cells))
                # Remove rows with 'Time' == 'Previous flights' or 'Next flights'
                if not (row_dict.get("Time") in ["Previous flights", "Next flights"]):
                    flights.append(row_dict)
        
        logger.info(f"Successfully fetched {len(flights)} flights for {iata} ({direction})")
        return {"iata": iata, "direction": direction, "flights": flights}
    
    except Exception as e:
        logger.error(f"Error parsing schedule data for {iata}: {e}")
        return {"error": "Unable to parse schedule data"}
