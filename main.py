import os
import random
from typing import List
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

IRSA_SIA_V2_ENDPOINT = "https://irsa.ipac.caltech.edu/SIA"
HIPS2FITS_ENDPOINT = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"

app = FastAPI(
    title="Sky Spotter API",
    description="Plataforma de telemetria astrométrica integrada ao protocolo IVOA SIA v2 da NASA e Supabase.",
    version="1.1.0"
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
    {"ra": "187.70", "dec": "12.39", "prefix": "SPH-CACHE"},
]

SURVEY_MAP = {
    "A": "CDS/P/DSS2/red",
    "B": "CDS/P/DSS2/blue",
}

def generate_fallback_starfield_svg(ra: str, dec: str, epoch: str) -> str:
    """Gera um recorte estelar SVG determinístico caso os servidores externos estejam indisponíveis."""
    rng = random.Random(f"{ra}:{dec}")
    stars = []
    for _ in range(95):
        cx = rng.randint(15, 485)
        cy = rng.randint(15, 485)
        r = round(rng.uniform(0.6, 2.4), 2)
        opacity = round(rng.uniform(0.35, 0.95), 2)
        stars.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#e2e8f0" opacity="{opacity}"/>')

    # Objeto transiente que muda de posição entre Época A e Época B
    tx_base = rng.randint(120, 360)
    ty_base = rng.randint(120, 360)
    tx = tx_base if epoch == "A" else tx_base + 22
    ty = ty_base if epoch == "A" else ty_base - 16
    transient = (
        f'<circle cx="{tx}" cy="{ty}" r="3.2" fill="#38bdf8" opacity="0.95"/>'
        f'<circle cx="{tx}" cy="{ty}" r="7" fill="#38bdf8" opacity="0.2"/>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">
      <rect width="500" height="500" fill="#030712"/>
      {''.join(stars)}
      {transient}
    </svg>"""

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
async def get_nasa_pair(request: Request):
    target = random.choice(TARGET_COORDINATES)
    ra = target["ra"]
    dec = target["dec"]
    image_id = f"{target['prefix']}-{ra}-{dec}"

    sia_status = "cached"
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            params = {"POS": f"CIRCLE {ra} {dec} 0.05", "COLLECTION": "wise_allwise_p3am_cdd", "RESPONSEFORMAT": "JSON"}
            res = await client.get(IRSA_SIA_V2_ENDPOINT, params=params)
            if res.status_code == 200:
                sia_status = "live_sia_v2"
    except Exception:
        sia_status = "fallback_cache"

    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    base_url = f"{proto}://{host}"

    return {
        "image_id": image_id,
        "ra": ra,
        "dec": dec,
        "source_protocol": sia_status,
        "image_a": f"{base_url}/api/sky-cutout?ra={ra}&dec={dec}&epoch=A",
        "image_b": f"{base_url}/api/sky-cutout?ra={ra}&dec={dec}&epoch=B"
    }

@app.get("/api/sky-cutout")
async def get_sky_cutout(ra: str, dec: str, epoch: str = "A"):
    survey = SURVEY_MAP.get(epoch.upper(), "CDS/P/DSS2/red")
    params = {
        "hips": survey,
        "width": 500,
        "height": 500,
        "fov": 0.25,
        "ra": ra,
        "dec": dec,
        "projection": "TAN",
        "format": "jpg"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            res = await client.get(HIPS2FITS_ENDPOINT, params=params)
            if res.status_code == 200 and len(res.content) > 1000:
                return Response(
                    content=res.content,
                    media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"}
                )
    except Exception:
        pass

    svg_content = generate_fallback_starfield_svg(ra, dec, epoch.upper())
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"}
    )

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