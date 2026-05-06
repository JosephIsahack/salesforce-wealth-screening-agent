from loguru import logger
from config import Config
from enrichment.fec import score_fec
from enrichment.sec_edgar import score_sec
from enrichment.propublica import score_propublica

_MIN_NAME_LENGTH = 4


class EnrichmentClient:
    """
    Thin facade that calls the three enrichment modules and returns a unified signals dict.
    All lookups are best-effort — failures are logged and never block scoring.
    """

    def __init__(self, config: Config):
        self.fec_api_key = config.fec_api_key or None

    def enrich(self, contact: dict) -> dict:
        """
        Returns {"fec": {...}, "sec_edgar": {...}, "propublica": {...}}.
        Any source that fails or finds nothing returns its zero-value dict.
        """
        first = (contact.get("FirstName") or "").strip()
        last = (contact.get("LastName") or "").strip()

        if len(first) < _MIN_NAME_LENGTH or len(last) < _MIN_NAME_LENGTH:
            return {}

        state = contact.get("MailingState") or None
        signals = {}

        for key, fn in [
            ("fec",        lambda: score_fec(first, last, state=state, api_key=self.fec_api_key)),
            ("sec_edgar",  lambda: score_sec(first, last)),
            ("propublica", lambda: score_propublica(first, last, state=state)),
        ]:
            try:
                signals[key] = fn()
            except Exception as e:
                logger.warning(f"{key.upper()} enrichment failed for {first} {last}: {e}")

        return signals
