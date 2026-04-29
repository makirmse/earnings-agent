"""Earnings call transcript scraper (Motley Fool).

Approach:
1. Hit fool.com's search endpoint for the ticker.
2. Filter results to /earnings/call-transcripts/YYYY/MM/DD/... URLs.
3. Disambiguate by ticker mentioned in the slug or article body.
4. Parse the transcript article body to plain text.

Motley Fool's HTML changes occasionally; the scraper logs a warning if it
finds zero candidates so we know to revisit selectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from .http import fool_client, fool_get

FOOL_BASE = "https://www.fool.com"
SEARCH_URL = FOOL_BASE + "/search/?q={query}"

TRANSCRIPT_PATH_RE = re.compile(
    r"/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/[^/?#]+/?",
    re.IGNORECASE,
)


@dataclass
class Transcript:
    url: str
    published: date
    ticker: str
    title: str
    body: str

    @property
    def slug(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def _candidate_urls(html: str) -> list[tuple[date, str]]:
    """Pull every /earnings/call-transcripts/YYYY/MM/DD/... link out of an
    HTML page along with its date."""
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[date, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = TRANSCRIPT_PATH_RE.search(href)
        if not m:
            continue
        url = urljoin(FOOL_BASE, href.split("?")[0].split("#")[0])
        if url in seen:
            continue
        seen.add(url)
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        out.append((d, url))
    return out


def search_transcripts(client: httpx.Client, ticker: str) -> list[tuple[date, str]]:
    """Return [(published_date, url), ...] candidates for a ticker, newest first."""
    queries = [
        f"{ticker} earnings call transcript",
        f"({ticker}) Q earnings call transcript",
    ]
    found: dict[str, date] = {}
    for q in queries:
        try:
            r = fool_get(client, SEARCH_URL.format(query=quote_plus(q)))
        except httpx.HTTPError:
            continue
        for d, url in _candidate_urls(r.text):
            # Only keep transcripts whose slug references the ticker.
            slug = url.rsplit("/", 2)[-2].lower()
            if ticker.lower() in slug.replace("-", " ").split():
                if url not in found or found[url] < d:
                    found[url] = d
    pairs = sorted(found.items(), key=lambda kv: kv[1], reverse=True)
    return [(d, u) for u, d in pairs]


def fetch_transcript(client: httpx.Client, url: str) -> Transcript:
    r = fool_get(client, url)
    soup = BeautifulSoup(r.text, "lxml")

    title = (soup.find("h1") or soup.title).get_text(strip=True) if soup.find("h1") or soup.title else url

    # Date: prefer <time datetime="...">, fall back to URL.
    pub: date | None = None
    t = soup.find("time")
    if t and t.get("datetime"):
        try:
            pub = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00")).date()
        except ValueError:
            pub = None
    if pub is None:
        m = TRANSCRIPT_PATH_RE.search(url)
        if m:
            pub = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if pub is None:
        pub = date.today()

    # Ticker: try to extract from a "(NASDAQ: AAPL)" pattern in the article.
    ticker_match = re.search(r"\(\s*[A-Z]{2,6}\s*:\s*([A-Z\.\-]{1,10})\s*\)", r.text)
    ticker = ticker_match.group(1) if ticker_match else ""

    # Body: the article content. Fool wraps transcript text in <article>; if
    # that's missing, fall back to the largest <div> by text length.
    article = soup.find("article")
    if article is None:
        candidates = soup.find_all("div")
        article = max(candidates, key=lambda d: len(d.get_text()), default=soup)
    for tag in article(["script", "style", "nav", "footer", "aside", "form"]):
        tag.decompose()
    body = article.get_text("\n", strip=True)

    return Transcript(url=url, published=pub, ticker=ticker, title=title, body=body)


def latest_transcripts(ticker: str, n: int = 4) -> list[Transcript]:
    out: list[Transcript] = []
    with fool_client() as c:
        candidates = search_transcripts(c, ticker)
        for _, url in candidates:
            if len(out) >= n:
                break
            try:
                tr = fetch_transcript(c, url)
            except httpx.HTTPError:
                continue
            # Sanity: skip transcripts that don't mention the ticker.
            if ticker.upper() not in tr.body.upper()[:5000]:
                continue
            out.append(tr)
    return out
