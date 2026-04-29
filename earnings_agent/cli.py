"""CLI for earnings-agent.

Examples:

  # Pull everything for AAPL into ./data/AAPL/
  SEC_USER_AGENT="Your Name your@email.com" \\
      earnings-agent fetch AAPL

  # Just SEC filings, last 365 days
  earnings-agent fetch AAPL --no-transcripts --no-presentations

  # Past two quarters only
  earnings-agent fetch AAPL --quarters 2
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import click
import httpx

from . import edgar, storage, transcripts
from .http import sec_client


def _log(msg: str) -> None:
    click.echo(msg, err=True)


@click.group()
def main() -> None:
    """Download SEC filings, earnings presentations, and call transcripts."""


@main.command("fetch")
@click.argument("ticker")
@click.option("--data-dir", default="data", type=click.Path(file_okay=False, path_type=Path),
              help="Output root directory (default: ./data)")
@click.option("--quarters", default=4, type=int,
              help="Number of recent quarters of 10-Q/10-K + transcripts to fetch.")
@click.option("--days", default=365, type=int,
              help="Window for 'all SEC filings' bucket (default: 365 days).")
@click.option("--filings/--no-filings", default=True,
              help="Download all filings in the date window.")
@click.option("--quarterlies/--no-quarterlies", default=True,
              help="Download the most recent 10-Q/10-K quarterly reports.")
@click.option("--presentations/--no-presentations", default=True,
              help="Download earnings 8-K exhibits (press release + slides).")
@click.option("--transcripts/--no-transcripts", "do_transcripts", default=True,
              help="Download earnings call transcripts from Motley Fool.")
def fetch(
    ticker: str,
    data_dir: Path,
    quarters: int,
    days: int,
    filings: bool,
    quarterlies: bool,
    presentations: bool,
    do_transcripts: bool,
) -> None:
    """Fetch all earnings artifacts for TICKER."""
    ticker = ticker.upper()
    data_dir = data_dir.resolve()
    _log(f"[{ticker}] resolving CIK from EDGAR")
    company = edgar.Company.from_ticker(ticker)
    _log(f"[{ticker}] {company.name} (CIK {company.cik})")

    storage.write_json(
        storage.root(data_dir, ticker) / "company.json",
        {"ticker": ticker, "cik": company.cik, "name": company.name,
         "synced": date.today().isoformat()},
    )

    manifest: dict = {
        "ticker": ticker,
        "name": company.name,
        "cik": company.cik,
        "synced": date.today().isoformat(),
        "sec_filings": [],
        "quarterly_reports": [],
        "earnings_8ks": [],
        "presentations": [],
        "transcripts": [],
        "errors": [],
    }

    _log(f"[{ticker}] fetching submissions index")
    all_filings = edgar.list_filings(company)
    _log(f"[{ticker}] {len(all_filings)} filings in submissions index")

    with sec_client() as sc:
        # 1. all SEC filings in window
        if filings:
            window = edgar.filings_in_window(all_filings, days=days)
            _log(f"[{ticker}] downloading {len(window)} filings from last {days} days")
            for f in window:
                try:
                    _download_full_filing(sc, company, f, data_dir, ticker)
                    manifest["sec_filings"].append(_filing_summary(f, company))
                except httpx.HTTPError as e:
                    msg = f"sec_filings {f.accession}: {e}"
                    _log(f"  ! {msg}")
                    manifest["errors"].append(msg)

        # 2. last N quarterly reports (10-Q/10-K) — already covered by (1)
        # if --filings is on; recorded separately for convenience.
        if quarterlies:
            quarterly = edgar.latest_quarterly_reports(all_filings, n=quarters)
            for f in quarterly:
                if not filings:
                    try:
                        _download_full_filing(sc, company, f, data_dir, ticker)
                    except httpx.HTTPError as e:
                        msg = f"quarterlies {f.accession}: {e}"
                        _log(f"  ! {msg}")
                        manifest["errors"].append(msg)
                        continue
                manifest["quarterly_reports"].append(_filing_summary(f, company))
            _log(f"[{ticker}] tagged {len(manifest['quarterly_reports'])} quarterly reports")

        # 3. earnings 8-Ks: press release + presentation exhibits
        if presentations:
            eights = edgar.earnings_8ks(all_filings, n=quarters)
            _log(f"[{ticker}] {len(eights)} earnings 8-Ks (item 2.02) in scope")
            pres_dir = storage.presentations_dir(data_dir, ticker)
            for f in eights:
                try:
                    exhibits = edgar.fetch_filing_index(sc, company, f)
                except httpx.HTTPError as e:
                    msg = f"earnings_8k_index {f.accession}: {e}"
                    _log(f"  ! {msg}")
                    manifest["errors"].append(msg)
                    continue

                summary = _filing_summary(f, company)
                summary["downloaded"] = []

                pr = edgar.pick_press_release_exhibit(exhibits)
                slides = edgar.pick_presentation_exhibits(exhibits)

                for ex in [e for e in (pr, *slides) if e]:
                    out_name = f"{f.filing_date.isoformat()}_{f.accession}_{ex['name']}"
                    dest = pres_dir / out_name
                    try:
                        size = edgar.download_file(sc, ex["url"], dest)
                        summary["downloaded"].append(
                            {"name": ex["name"], "url": ex["url"],
                             "path": str(dest.relative_to(data_dir)), "bytes": size}
                        )
                        _log(f"  + {dest.relative_to(data_dir)} ({size} B)")
                    except httpx.HTTPError as e:
                        msg = f"presentation {f.accession} {ex['name']}: {e}"
                        _log(f"  ! {msg}")
                        manifest["errors"].append(msg)
                manifest["earnings_8ks"].append(summary)

    # 4. transcripts
    if do_transcripts:
        _log(f"[{ticker}] searching Motley Fool for last {quarters} transcripts")
        try:
            trs = transcripts.latest_transcripts(ticker, n=quarters)
        except httpx.HTTPError as e:
            _log(f"  ! transcripts search failed: {e}")
            manifest["errors"].append(f"transcripts_search: {e}")
            trs = []

        if not trs:
            _log("  ! no transcripts found — fool.com search returned no candidates")

        tr_dir = storage.transcripts_dir(data_dir, ticker)
        for tr in trs:
            fname = f"{tr.published.isoformat()}_{tr.slug}.txt"
            dest = tr_dir / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            header = f"# {tr.title}\n# {tr.url}\n# Published: {tr.published.isoformat()}\n\n"
            dest.write_text(header + tr.body)
            manifest["transcripts"].append({
                "url": tr.url,
                "published": tr.published.isoformat(),
                "title": tr.title,
                "ticker": tr.ticker,
                "path": str(dest.relative_to(data_dir)),
                "chars": len(tr.body),
            })
            _log(f"  + {dest.relative_to(data_dir)} ({len(tr.body)} chars)")

    storage.write_json(storage.root(data_dir, ticker) / "manifest.json", manifest)
    _log(f"[{ticker}] done. manifest: {storage.root(data_dir, ticker) / 'manifest.json'}")


def _filing_summary(f: edgar.Filing, company: edgar.Company) -> dict:
    return {
        "form": f.form,
        "accession": f.accession,
        "filing_date": f.filing_date.isoformat(),
        "report_date": f.report_date.isoformat() if f.report_date else None,
        "fiscal_label": edgar.fiscal_label(f),
        "items": f.items,
        "primary_url": f.primary_url(company.cik_int),
    }


def _download_full_filing(
    client: httpx.Client,
    company: edgar.Company,
    f: edgar.Filing,
    data_dir: Path,
    ticker: str,
) -> None:
    out_dir = storage.filing_dir(data_dir, ticker, f.form, f.filing_date, f.accession)
    if (out_dir / f.primary_document).exists():
        return  # already downloaded
    primary = f.primary_url(company.cik_int)
    edgar.download_file(client, primary, out_dir / f.primary_document)

    try:
        exhibits = edgar.fetch_filing_index(client, company, f)
        storage.write_json(out_dir / "index.json", exhibits)
    except httpx.HTTPError:
        pass
    _log(f"  + {out_dir.relative_to(data_dir)}/{f.primary_document}")


@main.command("info")
@click.argument("ticker")
def info(ticker: str) -> None:
    """Print CIK + recent filings summary for TICKER (no downloads)."""
    company = edgar.Company.from_ticker(ticker)
    click.echo(f"{company.ticker}  {company.name}  CIK {company.cik}")
    filings = edgar.list_filings(company)
    quarterly = edgar.latest_quarterly_reports(filings, n=4)
    eights = edgar.earnings_8ks(filings, n=4)
    click.echo(f"\nLast 4 quarterly reports:")
    for f in quarterly:
        click.echo(f"  {edgar.fiscal_label(f):>10}  {f.form:5}  filed {f.filing_date}  acc {f.accession}")
    click.echo(f"\nLast 4 earnings 8-Ks (item 2.02):")
    for f in eights:
        click.echo(f"  filed {f.filing_date}  items {f.items}  acc {f.accession}")


if __name__ == "__main__":
    main()
