"""
DatasetConfig: one config per PDF ingestion run.
All dimensions needed for the allotments table are captured here,
so the pipeline is fully reusable across years, rounds, and state counsellings.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatasetConfig:
    # --- Required ---
    year: int
    counselling_type: str          # "AIQ" | "STATE"
    round: int
    pdf_path: str

    # --- Optional ---
    counselling_state: Optional[str] = None   # e.g. "Karnataka" (STATE only)
    start_page: int = 2                        # page 1 is legend, skip it
    end_page: Optional[int] = None             # None = process all pages
    test_mode_pages: Optional[int] = None      # e.g. 10 → process only 10 pages

    def dataset_key(self) -> str:
        """Stable unique key used for resume tracking."""
        parts = [
            str(self.year),
            self.counselling_type,
            self.counselling_state or "AIQ",
            str(self.round),
        ]
        return "|".join(parts)

    def effective_end_page(self, total_pages: int) -> int:
        if self.test_mode_pages is not None:
            return self.start_page + self.test_mode_pages - 1
        if self.end_page is not None:
            return self.end_page
        return total_pages

    def validate(self) -> None:
        assert self.year > 2000, "year must be > 2000"
        assert self.counselling_type in ("AIQ", "STATE"), \
            "counselling_type must be 'AIQ' or 'STATE'"
        assert self.round >= 1, "round must be >= 1"
        assert self.pdf_path.endswith(".pdf"), "pdf_path must end with .pdf"
        if self.counselling_type == "STATE":
            assert self.counselling_state, \
                "counselling_state is required for STATE counselling"
