"""Pydantic models for Winds Aloft forecasts."""

from typing import List, Optional

from pydantic import BaseModel, Field


class WindLevel(BaseModel):
    altitude_ft: int = Field(..., description="Altitude in feet MSL")
    wind_direction: Optional[int] = Field(None, description="Wind direction in degrees true (0-360)")
    wind_speed_kt: Optional[int] = Field(None, description="Wind speed in knots")
    temperature_c: Optional[int] = Field(None, description="Temperature in degrees Celsius")
    light_and_variable: bool = Field(False, description="True if winds are light and variable (< 5 kt)")
    raw: str = Field(..., description="Raw encoded wind data for this level")


class WindsAloftResponse(BaseModel):
    station: str = Field(..., description="FB winds station identifier (3-letter)")
    icao: str = Field(..., description="Requested ICAO code")
    forecast_hour: int = Field(..., description="Forecast period (6, 12, or 24 hours)")
    level: str = Field(..., description="Altitude range: low (up to FL240) or high (FL240-FL450)")
    valid_time: Optional[str] = Field(None, description="Forecast valid time (UTC)")
    winds: List[WindLevel] = Field(default_factory=list, description="Wind data at each altitude level")
    raw_text: Optional[str] = Field(None, description="Full raw FB winds text line for this station")
