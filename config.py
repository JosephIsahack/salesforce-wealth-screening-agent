import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    sf_username: str
    sf_password: str
    sf_security_token: str
    sf_domain: str
    sf_wealth_score_field: str
    sf_processed_field: str
    sf_alert_owner_id: str
    anthropic_api_key: str
    fec_api_key: str
    poll_interval_seconds: int
    high_value_threshold: int


def load_config() -> Config:
    required = [
        "SF_USERNAME",
        "SF_PASSWORD",
        "SF_SECURITY_TOKEN",
        "SF_ALERT_OWNER_ID",
        "ANTHROPIC_API_KEY",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    return Config(
        sf_username=os.environ["SF_USERNAME"],
        sf_password=os.environ["SF_PASSWORD"],
        sf_security_token=os.environ["SF_SECURITY_TOKEN"],
        sf_domain=os.getenv("SF_DOMAIN", "login"),
        sf_wealth_score_field=os.getenv("SF_WEALTH_SCORE_FIELD", "Wealth_Score__c"),
        sf_processed_field=os.getenv("SF_PROCESSED_FIELD", "Wealth_Scan_Processed__c"),
        sf_alert_owner_id=os.environ["SF_ALERT_OWNER_ID"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        fec_api_key=os.getenv("FEC_API_KEY", ""),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        high_value_threshold=int(os.getenv("HIGH_VALUE_THRESHOLD", "80")),
    )
