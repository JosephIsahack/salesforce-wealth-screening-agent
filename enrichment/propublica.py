"""
ProPublica Nonprofit Explorer enrichment.
Searches for foundations/orgs associated with a person by name or employer.

API: https://projects.propublica.org/nonprofits/api/v2/
No API key required. Courtesy rate limit: 1 req/sec.
"""
import logging
import time
from typing import Optional

import requests
import diskcache
from tenacity import retry, stop_after_attempt, wait_exponential

from matching.fuzzy import normalize_name

logger = logging.getLogger(__name__)

SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"
ORG_URL = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
CACHE_DIR = "./cache/propublica"
CACHE_TTL = 60 * 60 * 24 * 30  # 30 days


def get_cache() -> diskcache.Cache:
    return diskcache.Cache(CACHE_DIR)


def _search_orgs(query: str, state: Optional[str] = None) -> dict:
    params = {"q": query}
    if state:
        params["state[id]"] = state
    resp = requests.get(SEARCH_URL, params=params, timeout=30)
    # ProPublica returns 404 with valid JSON on 0 results
    if resp.status_code == 404:
        return {"organizations": []}
    if not resp.ok:
        resp.raise_for_status()
    time.sleep(0.5)
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
def _get_org_detail(ein: str) -> dict:
    resp = requests.get(ORG_URL.format(ein=ein), timeout=30)
    if not resp.ok:
        resp.raise_for_status()
    time.sleep(1)
    return resp.json()


def _get_org_assets(ein: str) -> float:
    try:
        detail = _get_org_detail(ein)
        filings = detail.get("filings_with_data", [])
        if filings:
            return float(filings[0].get("totassetsend", 0) or 0)
    except Exception as e:
        logger.debug(f"Could not fetch org detail for EIN {ein}: {e}")
    return 0.0


def search_person_orgs(
    first_name: str,
    last_name: str,
    employer: Optional[str] = None,
    state: Optional[str] = None,
) -> list[dict]:
    """
    Search for nonprofit orgs associated with this person via:
    1. Foundations named after them (e.g. "Smith Foundation", "Smith Family Foundation")
    2. Their employer org name
    Returns list of org dicts. Cached for 30 days.
    """
    cache_key = f"propublica:{last_name.lower()}:{first_name.lower()}"

    with get_cache() as cache:
        if cache_key in cache:
            logger.debug(f"ProPublica cache hit: {first_name} {last_name}")
            return cache[cache_key]

    matches = []
    seen_eins = set()

    def add_org(org: dict, match_type: str):
        ein = org.get("ein")
        if not ein or ein in seen_eins:
            return
        seen_eins.add(ein)
        assets = _get_org_assets(str(ein))
        matches.append({
            "ein": ein,
            "org_name": org.get("name", ""),
            "org_city": org.get("city", ""),
            "org_state": org.get("state", ""),
            "org_assets": assets,
            "org_revenue": float(org.get("totrevenue", 0) or 0),
            "match_type": match_type,
        })

    for q in [f"{last_name} Foundation", f"{last_name} Family Foundation", f"{last_name} Charitable"]:
        try:
            data = _search_orgs(q, state)
            for org in (data.get("organizations") or [])[:5]:
                if normalize_name(last_name) in normalize_name(org.get("name", "")):
                    add_org(org, "named_foundation")
        except Exception as e:
            logger.warning(f"ProPublica search failed for '{q}': {e}")

    if employer and len(employer) > 3:
        try:
            data = _search_orgs(employer, state)
            for org in (data.get("organizations") or [])[:3]:
                add_org(org, "employer_org")
        except Exception as e:
            logger.warning(f"ProPublica employer search failed for '{employer}': {e}")

    with get_cache() as cache:
        cache.set(cache_key, matches, expire=CACHE_TTL)

    logger.debug(f"ProPublica: {first_name} {last_name} → {len(matches)} org matches")
    return matches


def score_propublica(
    first_name: str,
    last_name: str,
    employer: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    """Search and score ProPublica results for a contact. Returns dict with scoring fields."""
    orgs = search_person_orgs(first_name, last_name, employer, state)

    if not orgs:
        return {
            "pp_found": False,
            "pp_is_officer": False,
            "pp_num_orgs": 0,
            "pp_total_assets": 0.0,
            "pp_largest_org_assets": 0.0,
            "pp_org_names": "",
        }

    total_assets = sum(o["org_assets"] for o in orgs)
    largest = max(o["org_assets"] for o in orgs)

    return {
        "pp_found": True,
        "pp_is_officer": True,
        "pp_num_orgs": len(orgs),
        "pp_total_assets": round(total_assets, 2),
        "pp_largest_org_assets": round(largest, 2),
        "pp_org_names": ", ".join(o["org_name"] for o in orgs[:5]),
    }
