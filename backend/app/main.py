"""
NEET-PG Counselling Analytics API
"""
import json, os
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import metadata, closing_ranks, allotments, institutes

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NEET-PG Counselling Analytics API",
    description="Extensible analytics engine for NEET-PG counselling allotment data.",
    version="1.0.0",
)

# Build CORS origins from environment variable + defaults
_default_origins = [
    "https://neetpg-counselling-v2.vercel.app",
    "http://localhost:3000",
]
_extra = os.getenv("CORS_ORIGINS", "")
_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metadata.router, prefix="/metadata", tags=["Metadata"])
app.include_router(closing_ranks.router, prefix="/closing-ranks", tags=["Closing Ranks"])
app.include_router(allotments.router, prefix="/allotments", tags=["Allotments"])
app.include_router(institutes.router, prefix="/institutes", tags=["Institutes"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.post("/save-zynerd-data", tags=["Temp"])
async def save_zynerd_data(request: FastAPIRequest):
    """Temporary: receive Zynerd institute data from browser and save to file."""
    body = await request.json()
    out_path = os.path.join(os.path.dirname(__file__), "../../zynerd_institutes.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    return {"ok": True, "count": len(body) if isinstance(body, list) else "saved"}


@app.get("/db-institutes", tags=["Temp"])
def get_db_institutes():
    """Temporary: serve DB institute data for browser comparison."""
    data_path = os.path.join(os.path.dirname(__file__), "../../backend/data/db_institutes.json")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)
