"""
SEC EDGAR full-text search enrichment.
Searches for a person's name in Form 4 (insider trading) and
DEF 14A (proxy statement / named executive) filings.

API: https://efts.sec.gov/LATEST/search-index
No API key required. SEC requests <= 10 req/sec with identifying User-Agent.
"""
import logging
import time
from typing import Optional

import requests
import diskcache
from tenacity import retry, stop_after_attempt, wait_exponential

from matching.fuzzy import build_name_variants, is_match

logger = logging.getLogger(__name__)

BASE_URL = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {"User-Agent": "amfAR-ProspectResearch/1.0 joseph.isahack@amfar.org"}
CACHE_DIR = "./cache/sec"
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


def get_cache() -> diskcache.Cache:
    return diskcache.Cache(CACHE_DIR)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def _search(query: str, forms: str = "4,DEF 14A", start_date: str = "2010-01-01") -> dict:
    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": start_date,
        "forms": forms,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    if not resp.ok:
        logger.warning(f"SEC EDGAR error {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
    return resp.json()


def search_person(first_name: str, last_name: str) -> list[dict]:
    """
    Search SEC EDGAR for a person's name in Form 4 and DEF 14A filings.
    Tries quoted full-name first, falls back to last-name-only if no hits.
    Results cached for 7 days.
    """
    cache_key = f"sec:{last_name.lower()}:{first_name.lower()}"

    with get_cache() as cache:
        if cache_key in cache:
            logger.debug(f"SEC cache hit: {first_name} {last_name}")
            return cache[cache_key]

    hits = []

    try:
        data = _search(f'"{first_name} {last_name}"')
        hits.extend(data.get("hits", {}).get("hits", []))
        time.sleep(0.15)
    except Exception as e:
        logger.warning(f"SEC search failed for {first_name} {last_name}: {e}")

    if not hits:
        try:
            data = _search(f'"{last_name}"')
            hits.extend(data.get("hits", {}).get("hits", []))
            time.sleep(0.15)
        except Exception as e:
            logger.warning(f"SEC fallback search failed for {last_name}: {e}")

    with get_cache() as cache:
        cache.set(cache_key, hits, expire=CACHE_TTL)

    logger.debug(f"SEC: {first_name} {last_name} → {len(hits)} raw hits")
    return hits


def score_sec(
    first_name: str,
    last_name: str,
    middle_name: Optional[str] = None,
) -> dict:
    """Search and score SEC EDGAR hits for a contact. Returns dict with scoring fields."""
    hits = search_person(first_name, last_name)
    name_variants = build_name_variants(first_name, last_name, middle_name)

    form4_hits = []
    defa_hits = []

    for hit in hits:
        source = hit.get("_source", {})
        form_type = source.get("form_type", "")
        snippets = hit.get("highlight", {}).get("file_contents", [])
        snippet_text = " ".join(snippets)

        matched = is_match(snippet_text, name_variants, threshold=75) or \
                  any(v.replace(' ', '') in snippet_text.lower().replace(' ', '') for v in name_variants)

        if not matched:
            continue

        entry = {
            "form_type": form_type,
            "entity_name": source.get("entity_name", ""),
            "file_date": source.get("file_date", ""),
        }

        if "4" in form_type and "DEF" not in form_type:
            form4_hits.append(entry)
        elif "DEF 14A" in form_type or "DEFA14A" in form_type:
            defa_hits.append(entry)

    if not form4_hits and not defa_hits:
        return {
            "sec_found": False,
            "sec_is_insider": False,
            "sec_is_executive": False,
            "sec_filing_count": 0,
            "sec_companies": "",
            "sec_most_recent_filing": None,
        }

    companies = list({h["entity_name"] for h in form4_hits + defa_hits if h["entity_name"]})
    all_dates = [h["file_date"] for h in form4_hits + defa_hits if h["file_date"]]
    most_recent = max(all_dates) if all_dates else None

    return {
        "sec_found": True,
        "sec_is_insider": len(form4_hits) > 0,
        "sec_is_executive": len(defa_hits) > 0,
        "sec_filing_count": len(form4_hits) + len(defa_hits),
        "sec_companies": ", ".join(companies[:5]),
        "sec_most_recent_filing": most_recent,
    }
