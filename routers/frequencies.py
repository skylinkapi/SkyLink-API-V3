
from fastapi import APIRouter, Query
from data_ingestion.remote_data import get_frequencies
from models.frequency import Frequency

router = APIRouter(prefix="/frequencies", tags=["frequencies"])

@router.get("/search", response_model=list[Frequency])
async def search_frequencies(icao: str = Query(...)):
    df = await get_frequencies()
    df = df[df['airport_ident'].str.upper() == icao.upper()]
    return df.replace({float('nan'): None}).to_dict(orient="records")
