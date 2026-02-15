
from fastapi import APIRouter, Query, HTTPException, status
from typing import List, Dict, Any, Optional
import pandas as pd
from data_ingestion.remote_data import get_airlines
from models.airline import Airline

router = APIRouter(prefix="/airlines", tags=["Airlines"])

@router.get(
    "/search", 
    response_model=List[Airline],
    responses={
        200: {
            "description": "List of matching airlines",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1355,
                            "name": "British Airways",
                            "alias": None,
                            "iata": "BA",
                            "icao": "BAW",
                            "callsign": "SPEEDBIRD",
                            "country": "United Kingdom",
                            "active": "Y",
                            "logo": "https://media.skylinkapi.com/logos/BA.png"
                        }
                    ]
                }
            }
        }
    }
)
async def search_airlines(
    icao: Optional[str] = Query(None, description="3-letter ICAO airline code", min_length=3, max_length=3),
    iata: Optional[str] = Query(None, description="2-letter IATA airline code", min_length=2, max_length=2)
) -> List[Dict[str, Any]]:
    """
    Search airlines by ICAO or IATA code.
    
    Returns airline information including name, country, callsign, and logo URL.
    
    - **icao**: 3-letter ICAO airline code (e.g., AAL for American Airlines)
    - **iata**: 2-letter IATA airline code (e.g., AA for American Airlines)
    """
    try:
        if not icao and not iata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either ICAO or IATA code must be provided"
            )
        
        df = await get_airlines()
        
        # Ensure proper column names
        if list(df.columns) == list(range(len(df.columns))):
            df.columns = [
                "id", "name", "alias", "iata", "icao", "callsign", "country", "active"
            ]
        
        # Filter by codes
        if icao:
            icao = icao.upper().strip()
            if len(icao) != 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ICAO code must be exactly 3 characters"
                )
            df = df[df['icao'].str.upper() == icao]
        
        if iata:
            iata = iata.upper().strip()
            if len(iata) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="IATA code must be exactly 2 characters"
                )
            df = df[df['iata'].str.upper() == iata]
        
        if df.empty:
            code = icao or iata
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No airlines found for code '{code}'"
            )
        
        # Convert to dict and add logo URLs
        airlines = df.replace({float('nan'): None, '\\N': None}).to_dict(orient="records")
        
        for airline in airlines:
            # Add logo URL if IATA code exists
            if airline.get('iata') and airline['iata'] not in [None, '', '\\N']:
                airline['logo'] = f"https://media.skylinkapi.com/logos/{airline['iata'].upper()}.png"
            else:
                airline['logo'] = None
        
        return airlines
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search airlines: {str(e)}"
        )
