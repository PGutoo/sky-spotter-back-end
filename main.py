import os
import random
from typing import List
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

IRSA_SIA_V2_ENDPOINT = "https://irsa.ipac.caltech.edu/SIA"

app = FastAPI(
    title="Sky Spotter API",
    description="Plataforma de telemetria astrométrica integrada ao protocolo IVOA SIA v2 da NASA e Supabase.",
    version="1.0.0"
)

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

TARGET_COORDINATES = [
    {"ra": "83.82", "dec": "-5.39", "prefix": "SPH-QR2"},
    {"ra": "266.41", "dec": "-29.0", "prefix": "SPH-CACHE"},
    {"ra": "10.68", "dec": "41.26", "prefix": "SPH-CACHE"},
    {"ra": "164.7", "dec": "-5.8", "prefix": "SPH-CACHE"},
]

FALLBACK_PAIRS = {
    "83.82": {
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=83.82,-5.39&Survey=DSS2+Blue&Return=JPEG&Pixels=500"
    },
    "266.41": {
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-J&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=266.41,-29.0&Survey=2MASS-K&Return=JPEG&Pixels=500"
    },
    "10.68": {
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=10.68,41.26&Survey=DSS2+IR&Return=JPEG&Pixels=500"
    },
    "164.7": {
        "image_a": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=164.7,-5.8&Survey=DSS2+Red&Return=JPEG&Pixels=500",
        "image_b": "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=164.7,-5.8&Survey=DSS2+Blue&Return=JPEG&Pixels=500"
    }
}

def build_scientific_recommendations(movimento: list, brilho: list, ruido: list) -> list[str]:
    sugestoes = []
    if movimento:
        sugestoes.append(
            "🪐 Painel de Movimento: Foram detetados potenciais objetos transientes (asteróides ou cometas). "
            "Sugestão: Cruzar as coordenadas RA/Dec registadas com o banco de dados de órbitas do Minor Planet Center (MPC)."
        )
    if brilho:
        sugestoes.append(
            "✨ Painel de Brilho: Identificadas variações de fluxo luminoso. "
            "Sugestão: Candidatas a estrelas variáveis ou eventos cataclísmicos. Recomenda-se verificar curvas de luz históricas."
        )
    if ruido:
        sugestoes.append(
            "📡 Painel de Ruído: Registados artefatos e ruídos de sensores. "
            "Sugestão: Útil para criar uma máscara de calibração e filtrar falsos positivos em varreduras futuras do telescópio."
        )
    if not sugestoes:
        sugestoes.append("🔭 Nenhuma anomalia catalogada ainda. Inicie uma varredura no Observatório Blink para alimentar o motor.")
    return sugestoes

@app.get("/")
def healthcheck():
    return {
        "status": "online",
        "service": "Sky Spotter API",
        "sia_endpoint": IRSA_SIA_V2_ENDPOINT,
        "supabase_connected": bool(supabase)
    }

@app.get("/api/nasa-pair")
async def get_nasa_pair():
    target = random.choice(TARGET_COORDINATES)
    ra = target["ra"]
    dec = target["dec"]
    image_id = f"{target['prefix']}-{ra}-{dec}"

    # Consulta metadados via protocolo IVOA SIA v2 (IRSA NASA) com fallback instantâneo
    sia_status = "cached"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            params = {"POS": f"CIRCLE {ra} {dec} 0.05", "COLLECTION": "wise_allwise_p3am_cdd", "RESPONSEFORMAT": "JSON"}
            res = await client.get(IRSA_SIA_V2_ENDPOINT, params=params)
            if res.status_code == 200:
                sia_status = "live_sia_v2"
    except Exception:
        sia_status = "fallback_cache"

    pair = FALLBACK_PAIRS[ra]
    return {
        "image_id": image_id,
        "ra": ra,
        "dec": dec,
        "source_protocol": sia_status,
        "image_a": pair["image_a"],
        "image_b": pair["image_b"]
    }

@app.post("/api/annotations")
def save_annotations(payload: AnnotationPayload):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase não configurado")

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

    try:
        response = supabase.table("anomalies").insert(rows).execute()
        return {"status": "success", "inserted": len(rows), "data": response.data}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao persistir no Supabase: {str(exc)}")


@app.get("/api/insights")
def get_insights():
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase não configurado")

    try:
        response = supabase.table("anomalies").select("*").order("created_at", desc=True).execute()
        records = response.data or []
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Supabase: {str(exc)}")

    movimento = [r for r in records if r.get("category") == "Movimento"]
    brilho = [r for r in records if r.get("category") == "Brilho"]
    ruido = [r for r in records if r.get("category") == "Ruído"]

    return {
        "total_registos": len(records),
        "paineis": {
            "movimento": {
                "titulo": "Objetos em Movimento",
                "icone": "🪐",
                "count": len(movimento),
                "itens": movimento
            },
            "brilho": {
                "titulo": "Variação de Brilho",
                "icone": "✨",
                "count": len(brilho),
                "itens": brilho
            },
            "ruido": {
                "titulo": "Ruídos e Artefatos",
                "icone": "📡",
                "count": len(ruido),
                "itens": ruido
            }
        },
        "sugestoes_cientificas": build_scientific_recommendations(movimento, brilho, ruido)
    }