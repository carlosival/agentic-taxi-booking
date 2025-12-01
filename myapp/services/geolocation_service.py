import httpx
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import List, Optional
from contextlib import asynccontextmanager
import os 

MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_TOKEN")

# 2. Pydantic Models (Data Validation)
class LocationParams(BaseModel):
    latitude: float
    longitude: float
    place: str

class GeocodeResponse(BaseModel):
    query: str
    results: List[LocationParams]


class MapboxService:
    BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

    def __init__(self, token = MAPBOX_ACCESS_TOKEN):
        self.token = token

    async def forward_geocode(self, address: str, limit: int = 1) -> List[LocationParams]:
        """
        Converts a text address into coordinates (Forward Geocoding).
        """
        url = f"{self.BASE_URL}/{address}.json"
        
        params = {
            "access_token": self.token,
            "limit": limit,
            "types": "place,address" # Optional: restrict results types
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail="Mapbox API Error")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        data = response.json()
        
        # Parse Mapbox GeoJSON response
        results = []
        for feature in data.get("features", []):
            # Mapbox returns [longitude, latitude]
            lon, lat = feature["center"]
            results.append(
                LocationParams(
                    longitude=lon, 
                    latitude=lat, 
                    place=feature["place_name"]
                )
            )
            
        return results


    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[LocationParams]:
        """
        Converts coordinates into a venue or address (Reverse Geocoding).
        """
        # Mapbox API URL structure for reverse geocoding: /{longitude},{latitude}.json
        url = f"{self.BASE_URL}/{longitude},{latitude}.json"
        
        params = {
            "access_token": self.token,
            "limit": 1,
            # 'poi' targets places/venues. 'address' targets streets.
            # Removing 'types' allows Mapbox to return the best match of any kind.
            "types": "poi,address" 
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail="Mapbox API Error")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        data = response.json()
        features = data.get("features", [])

        if not features:
            return None

        # Return the top result
        top_result = features[0]
        lon, lat = top_result["center"]
        
        return LocationParams(
            longitude=lon,
            latitude=lat,
            place_name=top_result["place_name"]
        )
    

