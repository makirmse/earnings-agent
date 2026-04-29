"""On-disk layout for downloaded artifacts.

data/
  <TICKER>/
    company.json            # CIK, name, last sync
    sec/
      <FORM>_<YYYY-MM-DD>_<accession>/
        <primary-doc>       # raw filing
        index.json          # exhibit list
    presentations/
      <YYYY-MM-DD>_<accession>_<exhibit>
    transcripts/
      <YYYY-MM-DD>_<slug>.txt
    manifest.json           # everything fetched in this run
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def root(base: Path, ticker: str) -> Path:
    return base / ticker.upper()


def sec_dir(base: Path, ticker: str) -> Path:
    return root(base, ticker) / "sec"


def presentations_dir(base: Path, ticker: str) -> Path:
    return root(base, ticker) / "presentations"


def transcripts_dir(base: Path, ticker: str) -> Path:
    return root(base, ticker) / "transcripts"


def filing_dir(base: Path, ticker: str, form: str, filing_date: date, accession: str) -> Path:
    safe_form = form.replace("/", "-")
    return sec_dir(base, ticker) / f"{safe_form}_{filing_date.isoformat()}_{accession}"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
