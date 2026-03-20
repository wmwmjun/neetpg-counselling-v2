"""
PDF parser for NEET-PG counselling allotment PDFs.

Round 1 — Expected column layout (1-indexed):
  1: SNo
  2: Rank
  3: Allotted Quota
  4: Allotted Institute
  5: Course
  6: Allotted Category
  7: Candidate Category
  8: Remarks

Round 2 — Expected column layout (1-indexed, after normalization to 12 cols):
  1:  Rank
  2:  R1 Allotted Quota
  3:  R1 Allotted Institute
  4:  R1 Course
  5:  R1 Remarks (status: Reported / Not Reported / Seat Surrendered …)
  6:  R2 Allotted Quota
  7:  R2 Allotted Institute
  8:  R2 Course
  9:  R2 Allotted Category
  10: R2 Candidate Category
  11: R2 Option No. (stored but not shown in UI)
  12: R2 Remarks

Round 3 — Expected column layout (1-indexed, after normalization to 16 cols):
  1:  Rank
  2:  R1 Allotted Quota (abbreviated)
  3:  R1 Allotted Institute (truncated)
  4:  R1 Course Id (abbreviated)
  5:  R1 Remarks
  6:  R2 Allotted Quota
  7:  R2 Allotted Institute (truncated)
  8:  R2 Course Id (abbreviated)
  9:  R2 Remarks
  10: R3 Allotted Quota
  11: R3 Allotted Institute (full name)
  12: R3 Course (full name)
  13: R3 Allotted Category
  14: R3 Candidate Category
  15: R3 Option No.
  16: R3 Remarks

Note: pdfplumber occasionally emits 13 columns for some Round-2 pages due to a
merged-cell artefact (a phantom None at index 6).  _normalize_r2_row() collapses
these back to 12 columns before processing.

Page 1 is the legend for R1/R2 — always skipped.
Pages 1-3 are legends for R3 — skipped by default (start_page=4).
Multi-line rows are merged: a row is a continuation if its anchor cell is
empty/non-numeric (SNo for R1, Rank for R2).
"""
from __future__ import annotations
import logging
import re
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Round 1 constants
# ---------------------------------------------------------------------------
EXPECTED_COLS = 8

COL_SNO = 0
COL_RANK = 1
COL_QUOTA = 2
COL_INSTITUTE = 3
COL_COURSE = 4
COL_ALLOTTED_CAT = 5
COL_CANDIDATE_CAT = 6
COL_REMARKS = 7

# ---------------------------------------------------------------------------
# Round 2 constants (0-based, after normalization to 12 cols)
# ---------------------------------------------------------------------------
EXPECTED_COLS_R2 = 12

R2_COL_RANK = 0
R2_COL_R1_QUOTA = 1
R2_COL_R1_INSTITUTE = 2
R2_COL_R1_COURSE = 3
R2_COL_R1_STATUS = 4      # R1 outcome: Reported / Not Reported / Seat Surrendered …
R2_COL_R2_QUOTA = 5
R2_COL_R2_INSTITUTE = 6
R2_COL_R2_COURSE = 7
R2_COL_R2_ALLOTTED_CAT = 8
R2_COL_R2_CANDIDATE_CAT = 9
R2_COL_R2_OPTION_NO = 10
R2_COL_R2_REMARKS = 11


def _is_sno(cell: Optional[str]) -> bool:
    """Return True if cell looks like a serial number (integer)."""
    if not cell:
        return False
    return bool(re.match(r'^\d+$', cell.strip()))


def _clean(cell: Optional[str]) -> Optional[str]:
    """Strip whitespace; return None for empty strings."""
    if cell is None:
        return None
    v = cell.strip()
    # Collapse internal whitespace
    v = re.sub(r'\s+', ' ', v)
    return v if v else None


def _merge_rows(raw_rows: list[list[Optional[str]]]) -> list[list[Optional[str]]]:
    """
    Merge continuation rows into the preceding base row.
    A continuation row has an empty SNo cell.
    Multi-line cell content is joined with a single space.
    """
    merged: list[list[Optional[str]]] = []
    for row in raw_rows:
        if row is None:
            continue
        # Pad / truncate to EXPECTED_COLS
        row = list(row) + [None] * EXPECTED_COLS
        row = row[:EXPECTED_COLS]

        cells = [_clean(c) for c in row]
        if _is_sno(cells[COL_SNO]):
            merged.append(cells)
        elif merged:
            # Append non-empty cells to the previous row
            prev = merged[-1]
            for i, cell in enumerate(cells):
                if cell:
                    if prev[i]:
                        prev[i] = prev[i] + " " + cell
                    else:
                        prev[i] = cell
        # else: orphaned continuation row before any base row — skip
    return merged


def _is_header_row(row: list[Optional[str]]) -> bool:
    """
    Detect repeated column header rows that appear on every PDF page.
    Heuristic: SNo cell contains 'sno' or 'sl' (case-insensitive).
    """
    sno_cell = (row[COL_SNO] or "").lower()
    return any(kw in sno_cell for kw in ("sno", "sl.no", "sl no", "s.no", "s no", "serial"))


def parse_pdf(
    pdf_path: str,
    start_page: int = 2,
    end_page: Optional[int] = None,
) -> Generator[tuple[int, list[Optional[str]]], None, None]:
    """
    Yield (page_num, row) for every valid data row in the PDF.
    page_num is 1-indexed (matching the PDF's visual page numbers).

    Parameters
    ----------
    pdf_path : str
    start_page : int   First page to process (1-indexed, default 2)
    end_page   : int   Last page inclusive (None = last page of PDF)
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required: pip install pdfplumber"
        ) from exc

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 4,
        "join_tolerance": 4,
        "edge_min_length": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        effective_end = min(end_page or total, total)

        logger.info(
            "PDF has %d pages. Processing pages %d–%d.",
            total, start_page, effective_end,
        )

        for page_idx in range(start_page - 1, effective_end):
            page_num = page_idx + 1
            page = pdf.pages[page_idx]

            try:
                tables = page.extract_tables(table_settings)
            except Exception as exc:
                logger.warning("Page %d: extract_tables failed: %s", page_num, exc)
                # Fallback: try text-based extraction
                tables = _fallback_text_parse(page)

            if not tables:
                logger.debug("Page %d: no tables found, skipping.", page_num)
                continue

            for table in tables:
                if not table:
                    continue
                merged = _merge_rows(table)
                for row in merged:
                    if _is_header_row(row):
                        continue
                    # Must have at least a rank value to be useful
                    if not _is_sno(row[COL_SNO]) and not row[COL_RANK]:
                        continue
                    yield page_num, row


# ---------------------------------------------------------------------------
# Round 2 helpers
# ---------------------------------------------------------------------------

def _normalize_r2_row(row: list) -> list:
    """
    Normalise a raw pdfplumber row to exactly EXPECTED_COLS_R2 (12) columns.

    pdfplumber sometimes produces 13 columns for Round-2 tables because the
    'Allotted Quota' header cell in the R2 section spans two physical columns
    on certain pages.  When this happens, index 6 is always None and the true
    R2 data is at indices 7–12.  We collapse by dropping index 6.
    """
    row = list(row)
    if len(row) == 13 and row[6] is None:
        row = row[:6] + row[7:]   # drop phantom col 6
    # Pad / truncate to 12
    row = row + [None] * EXPECTED_COLS_R2
    return row[:EXPECTED_COLS_R2]


def _is_rank(cell: Optional[str]) -> bool:
    """Return True if cell looks like a rank / serial number (positive integer)."""
    if not cell:
        return False
    return bool(re.match(r'^\d+$', cell.strip()))


def _merge_r2_rows(raw_rows: list[list[Optional[str]]]) -> list[list[Optional[str]]]:
    """
    Merge continuation rows for Round-2 tables.
    A row is a continuation if its Rank cell (col 0) is empty/non-numeric.
    """
    merged: list[list[Optional[str]]] = []
    for row in raw_rows:
        if row is None:
            continue
        row = _normalize_r2_row(row)
        cells = [_clean(c) for c in row]
        if _is_rank(cells[R2_COL_RANK]):
            merged.append(cells)
        elif merged:
            prev = merged[-1]
            for i, cell in enumerate(cells):
                if cell:
                    if prev[i]:
                        prev[i] = prev[i] + " " + cell
                    else:
                        prev[i] = cell
    return merged


def _is_r2_header_row(row: list[Optional[str]]) -> bool:
    """Detect repeated column-header rows in Round-2 PDFs."""
    rank_cell = (row[R2_COL_RANK] or "").lower()
    return any(kw in rank_cell for kw in ("rank", "sno", "sl.no", "s.no"))


def parse_round2_pdf(
    pdf_path: str,
    start_page: int = 2,
    end_page: Optional[int] = None,
) -> Generator[tuple[int, list[Optional[str]]], None, None]:
    """
    Yield (page_num, row) for every valid data row in a Round-2 PDF.
    Each row has EXPECTED_COLS_R2 (12) normalised columns (see module docstring).
    page_num is 1-indexed.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required: pip install pdfplumber") from exc

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 4,
        "join_tolerance": 4,
        "edge_min_length": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        effective_end = min(end_page or total, total)

        logger.info(
            "Round-2 PDF has %d pages. Processing pages %d–%d.",
            total, start_page, effective_end,
        )

        for page_idx in range(start_page - 1, effective_end):
            page_num = page_idx + 1
            page = pdf.pages[page_idx]

            try:
                tables = page.extract_tables(table_settings)
            except Exception as exc:
                logger.warning("Page %d: extract_tables failed: %s", page_num, exc)
                tables = []

            if not tables:
                logger.debug("Page %d: no tables found, skipping.", page_num)
                continue

            for table in tables:
                if not table:
                    continue
                merged = _merge_r2_rows(table)
                for row in merged:
                    if _is_r2_header_row(row):
                        continue
                    if not _is_rank(row[R2_COL_RANK]):
                        continue
                    yield page_num, row


# ---------------------------------------------------------------------------
# Round 3 constants (0-based, after normalization to 16 cols)
# ---------------------------------------------------------------------------
EXPECTED_COLS_R3 = 16

R3_COL_RANK = 0
R3_COL_R1_QUOTA = 1
R3_COL_R1_INSTITUTE = 2
R3_COL_R1_COURSE = 3
R3_COL_R1_REMARKS = 4
R3_COL_R2_QUOTA = 5
R3_COL_R2_INSTITUTE = 6
R3_COL_R2_COURSE = 7
R3_COL_R2_REMARKS = 8
R3_COL_R3_QUOTA = 9
R3_COL_R3_INSTITUTE = 10
R3_COL_R3_COURSE = 11
R3_COL_R3_ALLOTTED_CAT = 12
R3_COL_R3_CANDIDATE_CAT = 13
R3_COL_R3_OPTION_NO = 14
R3_COL_R3_REMARKS = 15


def _normalize_r3_row(row: list) -> list:
    """
    Normalise a raw pdfplumber row to exactly EXPECTED_COLS_R3 (16) columns.
    Handles potential extra columns from merged-cell artefacts.
    """
    row = list(row)
    # If extra columns, try to drop obvious None phantom columns
    while len(row) > EXPECTED_COLS_R3:
        # Find first None after col 0 that looks like a phantom
        removed = False
        for i in range(1, len(row)):
            if row[i] is None and i not in (R3_COL_R2_REMARKS, R3_COL_R3_REMARKS):
                row = row[:i] + row[i+1:]
                removed = True
                break
        if not removed:
            break
    # Pad / truncate to 16
    row = row + [None] * EXPECTED_COLS_R3
    return row[:EXPECTED_COLS_R3]


def _merge_r3_rows(raw_rows: list[list[Optional[str]]]) -> list[list[Optional[str]]]:
    """
    Merge continuation rows for Round-3 tables.
    A row is a continuation if its Rank cell (col 0) is empty/non-numeric.
    """
    merged: list[list[Optional[str]]] = []
    for row in raw_rows:
        if row is None:
            continue
        row = _normalize_r3_row(row)
        cells = [_clean(c) for c in row]
        if _is_rank(cells[R3_COL_RANK]):
            merged.append(cells)
        elif merged:
            prev = merged[-1]
            for i, cell in enumerate(cells):
                if cell:
                    if prev[i]:
                        prev[i] = prev[i] + " " + cell
                    else:
                        prev[i] = cell
    return merged


def _is_r3_header_row(row: list[Optional[str]]) -> bool:
    """Detect repeated column-header rows in Round-3 PDFs."""
    rank_cell = (row[R3_COL_RANK] or "").lower()
    return any(kw in rank_cell for kw in ("rank", "sno", "sl.no", "s.no", "counselling", "round"))


def parse_round3_pdf(
    pdf_path: str,
    start_page: int = 4,
    end_page: Optional[int] = None,
) -> Generator[tuple[int, list[Optional[str]]], None, None]:
    """
    Yield (page_num, row) for every valid data row in a Round-3 PDF.
    Each row has EXPECTED_COLS_R3 (16) normalised columns.
    page_num is 1-indexed.

    Round-3 PDF has 16 columns:
      Col 0:    Rank
      Cols 1-4: Round 1 (Quota abbrev, Institute, Course Id, Remarks)
      Cols 5-8: Round 2 (Quota, Institute, Course Id, Remarks)
      Cols 9-15: Round 3 (Quota, Institute, Course, Allotted Cat, Candidate Cat, Option No, Remarks)

    Pages 1-3 are legend tables — skipped by default (start_page=4).
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required: pip install pdfplumber") from exc

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 4,
        "join_tolerance": 4,
        "edge_min_length": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }

    import gc

    # Get total page count with a quick open/close
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
    effective_end = min(end_page or total, total)

    logger.info(
        "Round-3 PDF has %d pages. Processing pages %d–%d.",
        total, start_page, effective_end,
    )

    # Process in batches to limit memory usage (pdfplumber holds all pages in memory)
    BATCH_SIZE = 50
    for batch_start_idx in range(start_page - 1, effective_end, BATCH_SIZE):
        batch_end_idx = min(batch_start_idx + BATCH_SIZE, effective_end)

        with pdfplumber.open(pdf_path, pages=list(range(batch_start_idx, batch_end_idx))) as pdf:
            for local_idx, page in enumerate(pdf.pages):
                page_num = batch_start_idx + local_idx + 1

                try:
                    tables = page.extract_tables(table_settings)
                except Exception as exc:
                    logger.warning("Page %d: extract_tables failed: %s", page_num, exc)
                    tables = []

                if not tables:
                    logger.debug("Page %d: no tables found, skipping.", page_num)
                    continue

                for table in tables:
                    if not table:
                        continue
                    merged = _merge_r3_rows(table)
                    for row in merged:
                        if _is_r3_header_row(row):
                            continue
                        if not _is_rank(row[R3_COL_RANK]):
                            continue
                        yield page_num, row

        gc.collect()


def _fallback_text_parse(page) -> list[list[list[Optional[str]]]]:
    """
    Fallback when line-based extraction fails.
    Use word-level extraction grouped by y-position.
    Returns in the same format as extract_tables() output.
    """
    try:
        words = page.extract_words(
            x_tolerance=3,
            y_tolerance=3,
            keep_blank_chars=False,
        )
    except Exception:
        return []

    if not words:
        return []

    # Group words by row (similar y0)
    rows_by_y: dict[int, list] = {}
    for w in words:
        y_key = round(w["top"] / 5) * 5   # bucket to 5pt
        rows_by_y.setdefault(y_key, []).append(w)

    # Sort each row by x position
    text_rows: list[list[Optional[str]]] = []
    for y in sorted(rows_by_y):
        row_words = sorted(rows_by_y[y], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in row_words)
        # Very rough split on 2+ spaces
        cols = re.split(r'  +', text)
        padded = cols + [None] * (EXPECTED_COLS - len(cols))
        text_rows.append(padded[:EXPECTED_COLS])

    return [text_rows] if text_rows else []
