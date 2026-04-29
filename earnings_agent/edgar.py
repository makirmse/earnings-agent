"""SEC EDGAR fetcher.

Downloads:
- All filings in a date window (default: trailing 365 days).
- The N most recent 10-Q / 10-K filings.
- Earnings-related 8-K exhibits (press release + presentation slides).

Identifiers:
- Tickers are resolved to CIKs via company_tickers.json.
- Filings are addressed by accession number, e.g. 0000320193-25-000005.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .http import sec_client, sec_get

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/"


@dataclass
class Filing:
    accession: str           # e.g. "0000320193-25-000005"
    form: str                # "10-Q", "10-K", "8-K", ...
    filing_date: date
    report_date: date | None  # period of report
    primary_document: str    # primary doc filename within the archive
    items: str = ""          # comma-separated 8-K items, e.g. "2.02,9.01"
    exhibits: list[dict] = field(default_factory=list)  # populated lazily

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    def archive_url(self, cik_int: int) -> str:
        return ARCHIVE_BASE.format(
            cik_int=cik_int, accession_nodash=self.accession_nodash
        )

    def primary_url(self, cik_int: int) -> str:
        return urljoin(self.archive_url(cik_int), self.primary_document)


@dataclass
class Company:
    cik: str          # zero-padded 10-digit
    cik_int: int
    ticker: str
    name: str

    @classmethod
    def from_ticker(cls, ticker: str) -> "Company":
        ticker = ticker.upper()
        with sec_client() as c:
            data = sec_get(c, TICKER_MAP_URL).json()
        for row in data.values():
            if row["ticker"].upper() == ticker:
                cik_int = int(row["cik_str"])
                return cls(
                    cik=f"{cik_int:010d}",
                    cik_int=cik_int,
                    ticker=row["ticker"].upper(),
                    name=row["title"],
                )
        raise ValueError(f"Ticker not found on EDGAR: {ticker}")


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def list_filings(company: Company) -> list[Filing]:
    """Return the recent filings index for a company."""
    url = SUBMISSIONS_URL.format(cik=company.cik)
    with sec_client() as c:
        data = sec_get(c, url).json()
    recent = data["filings"]["recent"]
    out: list[Filing] = []
    n = len(recent["accessionNumber"])
    for i in range(n):
        out.append(
            Filing(
                accession=recent["accessionNumber"][i],
                form=recent["form"][i],
                filing_date=_parse_date(recent["filingDate"][i]) or date.min,
                report_date=_parse_date(recent.get("reportDate", [""] * n)[i]),
                primary_document=recent["primaryDocument"][i],
                items=recent.get("items", [""] * n)[i] or "",
            )
        )
    return out


def filings_in_window(
    filings: Iterable[Filing], days: int = 365, today: date | None = None
) -> list[Filing]:
    today = today or date.today()
    cutoff = today - timedelta(days=days)
    return [f for f in filings if f.filing_date >= cutoff]


def latest_n(filings: Iterable[Filing], form: str, n: int) -> list[Filing]:
    matches = [f for f in filings if f.form == form]
    matches.sort(key=lambda f: f.filing_date, reverse=True)
    return matches[:n]


def latest_quarterly_reports(filings: Iterable[Filing], n: int = 4) -> list[Filing]:
    """Return the most recent N quarterly-style reports.

    Real fiscal years have 3 10-Qs and 1 10-K. To get "the last 4 quarters"
    of reports, we take 10-Q + 10-K and pick the N most recent.
    """
    filings = list(filings)
    matches = [f for f in filings if f.form in ("10-Q", "10-K")]
    matches.sort(key=lambda f: (f.report_date or f.filing_date), reverse=True)
    return matches[:n]


def earnings_8ks(filings: Iterable[Filing], n: int = 4) -> list[Filing]:
    """8-Ks tagged with item 2.02 (Results of Operations) — earnings releases."""
    matches = [
        f for f in filings if f.form == "8-K" and "2.02" in (f.items or "")
    ]
    matches.sort(key=lambda f: f.filing_date, reverse=True)
    return matches[:n]


# ---- exhibit discovery ---------------------------------------------------


def fetch_filing_index(client: httpx.Client, company: Company, filing: Filing) -> list[dict]:
    """Parse the filing index page to enumerate every document in the filing.

    Returns a list of {name, url, type, description} dicts.
    """
    idx_url = filing.archive_url(company.cik_int) + "index.json"
    r = sec_get(client, idx_url)
    data = r.json()
    items = data.get("directory", {}).get("item", [])
    out = []
    base = filing.archive_url(company.cik_int)
    for it in items:
        name = it.get("name", "")
        if name.endswith(("/",)):
            continue
        out.append(
            {
                "name": name,
                "url": urljoin(base, name),
                "type": it.get("type", ""),
                "size": it.get("size", ""),
            }
        )
    return out


PRESENTATION_HINTS = (
    "presentation",
    "slide",
    "deck",
    "investor",
    "supplement",
)
PRESENTATION_EXTS = (".pdf",)


def pick_presentation_exhibits(exhibits: list[dict]) -> list[dict]:
    """Heuristically pick presentation/slide exhibits from an 8-K's filelist.

    Strategy:
    1. Prefer files whose name contains a presentation hint (presentation,
       slide, deck, investor, supplement).
    2. Otherwise fall back to any PDF exhibits (slides are usually PDFs).
    """
    by_hint = [
        e for e in exhibits
        if any(h in e["name"].lower() for h in PRESENTATION_HINTS)
    ]
    if by_hint:
        return by_hint
    return [e for e in exhibits if e["name"].lower().endswith(PRESENTATION_EXTS)]


def pick_press_release_exhibit(exhibits: list[dict]) -> dict | None:
    """Earnings press release is typically Exhibit 99.1 (often ex-99.1.htm)."""
    for e in exhibits:
        n = e["name"].lower()
        if "99-1" in n or "99_1" in n or "ex991" in n or "ex-99.1" in n or "99.1" in n:
            if n.endswith((".htm", ".html", ".txt")):
                return e
    return None


# ---- download ------------------------------------------------------------


def download_file(client: httpx.Client, url: str, dest_path) -> int:
    r = sec_get(client, url)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(r.content)
    return len(r.content)


# ---- helpers for naming --------------------------------------------------


def fiscal_label(filing: Filing) -> str:
    """Best-effort 'YYYY-Qn' label from report_date for 10-Q/10-K."""
    rd = filing.report_date
    if not rd:
        return filing.filing_date.isoformat()
    if filing.form == "10-K":
        return f"{rd.year}-FY"
    q = (rd.month - 1) // 3 + 1
    return f"{rd.year}-Q{q}"


def html_to_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def to_jsonable(obj):
    """Recursively convert dataclasses / dates / sets for json.dump."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: to_jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return obj


def dumps(obj) -> str:
    return json.dumps(to_jsonable(obj), indent=2, default=str)
