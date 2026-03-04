"""
PDF parser for NEET-PG counselling allotment PDFs.

Expected column layout (1-indexed):
  1: SNo
  2: Rank
  3: Allotted Quota
  4: Allotted Institute
  5: Course
  6: Allotted Category
  7: Candidate Category
  8: Remarks

Page 1 is the legend — always skipped.
Multi-line rows are merged: a row is a continuation if its SNo cell is empty/non-numeric.
"""
from __future__ import annotations
import logging
import re
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# Expected column count in the PDF table
EXPECTED_COLS = 8

# Column indices (0-based)
COL_SNO = 0
COL_RANK = 1
COL_QUOTA = 2
COL_INSTITUTE = 3
COL_COURSE = 4
COL_ALLOTTED_CAT = 5
COL_CANDIDATE_CAT = 6
COL_REMARKS = 7


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
