import os
import random
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = FastAPI(title="Sky Spotter API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MarkerItem(BaseModel):
    x: float
    y: float
    category: str

class AnnotationPayload(BaseModel):
    image_id: str
    ra: str
    dec: str
    annotations: List[MarkerItem]

SKY_CATALOG_PAIRS = [
    {
        "image_id": "SPH-QR2-83.82--5.39",
        "ra": "83.82",
        "dec": "-5.39",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Blue&Return=JPEG&Pixels=500"
    },
    {
        "image_id": "SPH-CACHE-266.41--29.0",
        "ra": "266.41",
        "dec": "-29.0",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-J&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-K&Return=JPEG&Pixels=500"
    },
    {
        "image_id": "SPH-CACHE-10.68-41.26",
        "ra": "10.68",
        "dec": "41.26",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+IR&Return=JPEG&Pixels=500"
    }
]

@app.get("/")
def healthcheck():
    return {"status": "online", "database": "connected" if supabase else "unconfigured"}

@app.get("/api/nasa-pair")
def get_nasa_pair():
    return random.choice(SKY_CATALOG_PAIRS)

@app.post("/api/annotations")
def save_annotations(payload: AnnotationPayload):
    if not supabase:
        raise HTTPException(status_code=500, detail="Credenciais do Supabase não configuradas no .env")

    rows = [
        {
            "image_id": payload.image_id,
            "ra": payload.ra,
            "dec": payload.dec,
            "x": marker.x,
            "y": marker.y,
            "category": marker.category
        }
        for marker in payload.annotations
    ]

    response = supabase.table("annotations").insert(rows).execute()
    return {"status": "success", "inserted": len(rows), "data": response.data}