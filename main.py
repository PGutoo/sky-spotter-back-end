import random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Sky Spotter API",
    description="Backend de telemetria astrométrica e integração NASA IVOA SIA v2",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SKY_CATALOG_PAIRS = [
    {
        "image_id": "SPH-QR2-83.82--5.39",
        "ra": "83.82",
        "dec": "-5.39",
        "target": "Orion Nebula Sector",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Blue&Return=JPEG&Pixels=500"
    },
    {
        "image_id": "SPH-CACHE-266.41--29.0",
        "ra": "266.41",
        "dec": "-29.0",
        "target": "Galactic Center Field",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-J&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-K&Return=JPEG&Pixels=500"
    },
    {
        "image_id": "SPH-CACHE-10.68-41.26",
        "ra": "10.68",
        "dec": "41.26",
        "target": "Andromeda Core Sector",
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+IR&Return=JPEG&Pixels=500"
    }
]

@app.get("/")
def healthcheck():
    return {"status": "online", "service": "Sky Spotter API"}

@app.get("/api/nasa-pair")
def get_nasa_pair():
    return random.choice(SKY_CATALOG_PAIRS)