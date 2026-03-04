"""
NEET-PG Counselling Analytics API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import metadata, closing_ranks, allotments

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NEET-PG Counselling Analytics API",
    description="Extensible analytics engine for NEET-PG counselling allotment data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metadata.router, prefix="/metadata", tags=["Metadata"])
app.include_router(closing_ranks.router, prefix="/closing-ranks", tags=["Closing Ranks"])
app.include_router(allotments.router, prefix="/allotments", tags=["Allotments"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
