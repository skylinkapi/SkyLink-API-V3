
from fastapi import APIRouter, Query
from data_ingestion.remote_data import get_navaids
from models.navaid import Navaid

router = APIRouter(prefix="/navaids", tags=["navaids"])

@router.get("/search", response_model=list[Navaid])
async def search_navaids(icao: str = Query(...)):
    df = await get_navaids()
    # Use associated_airport for ICAO search
    if 'associated_airport' in df.columns:
        df = df[df['associated_airport'].str.upper() == icao.upper()]
    # Only return columns present in the model
    model_fields = set(Navaid.__fields__.keys())
    df = df[[col for col in df.columns if col in model_fields]]
    return df.replace({float('nan'): None}).to_dict(orient="records")
