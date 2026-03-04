# NEET-PG Counselling Analytics Tool

An extensible, production-grade analytics engine for NEET-PG counselling allotment data.

**MVP scope**: AIQ (All India Counselling) · 2025 · Round 1 · Closing Rank analytics + drill-down allotment view.

---

## Architecture Overview

```
neetpg-counselling-v2/
├── backend/                    # Python · FastAPI · SQLAlchemy · SQLite
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── database.py         # Engine + session factory (swap to PostgreSQL via DATABASE_URL)
│   │   ├── models.py           # ORM models (allotments, ref_courses, ingestion_errors, progress)
│   │   ├── schemas.py          # Pydantic v2 request/response schemas
│   │   └── routers/
│   │       ├── metadata.py     # GET /metadata
│   │       ├── closing_ranks.py # GET /closing-ranks, GET /closing-ranks/:group_id/allotments
│   │       └── allotments.py   # GET /allotments
│   ├── ingestion/
│   │   ├── config.py           # DatasetConfig dataclass
│   │   ├── normalizers.py      # Quota / category / state / course normalisation
│   │   ├── pdf_parser.py       # pdfplumber-based PDF table extractor
│   │   └── pipeline.py         # Resume-safe ingestion pipeline
│   └── scripts/
│       ├── init_db.py          # Create all DB tables
│       └── ingest.py           # CLI ingestion runner
├── frontend/                   # Next.js 14 · TypeScript · Tailwind CSS
│   └── src/
│       ├── app/page.tsx        # Main page (filter state, data fetching)
│       ├── components/
│       │   ├── FilterBar.tsx   # Sticky top filter bar
│       │   ├── ClosingRankGrid.tsx  # Sortable, paginated closing-rank table
│       │   └── DrillDownModal.tsx   # Allotment drill-down modal
│       └── lib/api.ts          # Typed API client
└── data/pdfs/                  # Place your PDF files here (gitignored)
```

---

## Extensibility Design

The schema and pipeline are designed so that **no schema rewrite is needed** to add:

| Expansion               | What to do                                               |
|-------------------------|----------------------------------------------------------|
| 2024 / 2023 data        | Run ingestion with `--year 2024 --round 1`               |
| Rounds 2–4              | Run ingestion with `--round 2` (or 3, 4)                 |
| State counselling       | Run ingestion with `--type STATE --state Karnataka`      |
| New year's PDF          | Run ingestion with `--year 2026`                         |

The `allotments` table stores all dimensions (`year`, `counselling_type`, `counselling_state`, `round`) and all API filters are parameterised.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- pip

### Backend setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialise the database
python -m scripts.init_db
```

### Ingest a PDF

Place the PDF at `data/pdfs/AIQ_2025_R1.pdf`, then:

```bash
cd backend

# Test mode: first 10 pages only
python -m scripts.ingest \
  --pdf ../data/pdfs/AIQ_2025_R1.pdf \
  --year 2025 --type AIQ --round 1 \
  --test-pages 10

# Full ingestion
python -m scripts.ingest \
  --pdf ../data/pdfs/AIQ_2025_R1.pdf \
  --year 2025 --type AIQ --round 1
```

The pipeline is **resume-safe**: if interrupted, re-running picks up from the last completed page.

### Start the API server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:3000

---

## API Reference

### `GET /metadata`
Returns available filter values (years, rounds, quotas, categories, states, courses).

**Query params**: `year`, `counselling_type`, `counselling_state`, `round`

### `GET /closing-ranks`
Returns grouped closing-rank rows. Closing rank is computed as `MAX(rank)` per group.

**Key query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `year` | 2025 | |
| `counselling_type` | AIQ | |
| `round` | 1 | |
| `quota_norm` | AI | Quota filter |
| `allotted_category_norm` | — | Category filter |
| `state` | — | State filter |
| `course_norm` | — | Course filter (partial match) |
| `rank_min` / `rank_max` | — | Rank range |
| `search` | — | Free text search (institute / course) |
| `sort_by` | institute_name | `institute_name` \| `course_norm` \| `closing_rank` |
| `sort_order` | asc | `asc` \| `desc` |
| `page` / `page_size` | 1 / 50 | Pagination |

### `GET /closing-ranks/{group_id}/allotments`
Returns all individual allotments for one closing-rank group, sorted by rank ascending.

`group_id` is a URL-safe base64-encoded key returned by `GET /closing-ranks`.

### `GET /allotments`
Returns raw allotment records with full filtering and pagination.

---

## Closing Rank Logic

Closing rank is **not stored** — it is dynamically computed as:

```sql
SELECT MAX(rank) AS closing_rank
FROM allotments
GROUP BY year, counselling_type, counselling_state, round,
         institute_name, course_norm, quota_norm, allotted_category_norm
```

This means closing ranks automatically update if re-ingestion adds new data.

---

## Normalisation Rules

### Quota
Controlled dictionary: `AI AM BH DU AD IP JM MM NR PS`
Unknown values → `quota_norm = "UNKNOWN"` + logged in `ingestion_errors`.
Default UI filter: `AI`.

### Category
Controlled values: `GN EW BC SC ST` and PwD variants (`GN-PwD`, `EW-PwD`, etc.)
`UR` / `GEN` / `UNRESERVED` → `GN`
`OBC` / `OBC-NCL` → `BC`

### State
Extracted from institute text via:
1. Substring match against India state list (longest match first)
2. Pincode inference (6-digit numbers in text)
3. `NULL` if not found

### Course
Format: `<DEGREE> <SPECIALTY>`
e.g. `M.D. (General Medicine)` → `MD GENERAL MEDICINE`

---

## Docker

```bash
# Copy your PDF into data/pdfs/ first
docker-compose up --build
```

Backend: http://localhost:8000
Frontend: http://localhost:3000

---

## Future Expansion

The UI includes placeholder columns in the closing-rank grid:
- CR R2, CR R3, CR R4 (other rounds)
- Fee, Stipend, Bond, Beds

These are ready to be populated as additional datasets are ingested.
