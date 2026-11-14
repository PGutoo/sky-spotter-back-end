from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Sky Spotter API",
    description="Backend de telemetria astrométrica e integração NASA IVOA SIA v2",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def healthcheck():
    return {"status": "online", "service": "Sky Spotter API", "protocol": "IVOA SIA v2"}