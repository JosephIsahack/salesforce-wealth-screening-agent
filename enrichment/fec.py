"""
FEC Political Donations enrichment.
Queries the OpenFEC API for Schedule A (individual contributions) records.
Contributions >= $200 are publicly disclosed.

API docs: https://api.open.fec.gov/developers/
Rate limit: 1,000 requests/hour with API key.
"""
import logging
import time
from datetime import datetime
from typing import Optional

import requests
import diskcache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from matching.fuzzy import build_name_variants, is_match, names_share_state

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open.fec.gov/v1/schedules/schedule_a/"
_DEFAULT_API_KEY = "AS5qJ86BnCP266mJGJxAhkk2wLk8IiFsxNZGCPzn"
CACHE_DIR = "./cache/fec"
CACHE_TTL = 60 * 60 * 24 * 30  # 30 days
MIN_AMOUNT = 200


def get_cache() -> diskcache.Cache:
    return diskcache.Cache(CACHE_DIR)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
)
def _fetch_page(
    contributor_name: str,
    api_key: str,
    contributor_state: Optional[str],
    last_index: Optional[str] = None,
    last_date: Optional[str] = None,
) -> dict:
    params = {
        "contributor_name": contributor_name,
        "min_amount": MIN_AMOUNT,
        "api_key": api_key,
        "per_page": 100,
        "sort": "-contribution_receipt_date",
    }
    if contributor_state:
        params["contributor_state"] = contributor_state
    if last_index and last_date:
        params["last_index"] = last_index
        params["last_contribution_receipt_date"] = last_date

    resp = requests.get(BASE_URL, params=params, timeout=60)
    if resp.status_code == 429:
        logger.warning("FEC rate limit hit, backing off...")
        resp.raise_for_status()
    if not resp.ok:
        logger.warning(f"FEC API error {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
    return resp.json()


def fetch_donations(
    first_name: str,
    last_name: str,
    state: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Pull all FEC Schedule A records matching this person.
    Uses keyset pagination. Results are cached for 30 days.
    """
    cache_key = f"fec:{last_name.lower()}:{first_name.lower()}:{(state or 'any').lower()}"
    _api_key = api_key or _DEFAULT_API_KEY

    with get_cache() as cache:
        if cache_key in cache:
            logger.debug(f"FEC cache hit: {first_name} {last_name}")
            return cache[cache_key]

    search_name = f"{last_name} {first_name}"
    all_records = []
    last_index = None
    last_date = None
    page = 0

    while True:
        try:
            data = _fetch_page(search_name, _api_key, state, last_index, last_date)
        except Exception as e:
            logger.warning(f"FEC fetch failed for {first_name} {last_name}: {e}")
            break

        results = data.get("results", [])
        all_records.extend(results)
        page += 1

        pagination = data.get("pagination", {})
        last_indexes = pagination.get("last_indexes") or {}
        next_index = last_indexes.get("last_index")
        next_date = last_indexes.get("last_contribution_receipt_date")

        if not next_index or len(results) < 100:
            break

        last_index = next_index
        last_date = next_date
        time.sleep(0.1)

    with get_cache() as cache:
        cache.set(cache_key, all_records, expire=CACHE_TTL)

    logger.debug(f"FEC: {first_name} {last_name} → {len(all_records)} raw records ({page} pages)")
    return all_records


def score_fec(
    first_name: str,
    last_name: str,
    state: Optional[str] = None,
    middle_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Fetch and score FEC donations for a contact. Returns dict with all scoring fields."""
    raw = fetch_donations(first_name, last_name, state, api_key)
    name_variants = build_name_variants(first_name, last_name, middle_name)

    matched = []
    for rec in raw:
        candidate_name = rec.get("contributor_name", "")
        candidate_state = rec.get("contributor_state", "")
        if not is_match(candidate_name, name_variants, threshold=85):
            continue
        if not names_share_state(state, candidate_state):
            continue
        matched.append(rec)

    if not matched:
        return {
            "fec_found": False,
            "fec_total_donated": 0.0,
            "fec_num_donations": 0,
            "fec_most_recent_year": None,
            "fec_recency_score": 0.0,
            "fec_employers": "",
        }

    total = sum(r.get("contribution_receipt_amount", 0) or 0 for r in matched)
    years = []
    for r in matched:
        d = r.get("contribution_receipt_date", "")
        if d and len(d) >= 4:
            try:
                years.append(int(d[:4]))
            except ValueError:
                pass

    most_recent = max(years) if years else None
    current_year = datetime.now().year
    if most_recent:
        age = current_year - most_recent
        if age <= 2:
            recency = 1.0
        elif age <= 5:
            recency = 0.7
        elif age <= 9:
            recency = 0.4
        else:
            recency = 0.2
    else:
        recency = 0.2

    employers = list({r.get("contributor_employer", "") for r in matched if r.get("contributor_employer")})

    return {
        "fec_found": True,
        "fec_total_donated": round(total, 2),
        "fec_num_donations": len(matched),
        "fec_most_recent_year": most_recent,
        "fec_recency_score": recency,
        "fec_employers": ", ".join(employers[:5]),
    }
