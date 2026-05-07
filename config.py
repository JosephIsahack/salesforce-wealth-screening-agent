import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    sf_username: str
    sf_consumer_key: str
    sf_private_key_file: str
    sf_wealth_score_field: str
    sf_processed_field: str
    sf_alert_owner_id: str
    ollama_base_url: str
    ollama_model: str
    fec_api_key: str
    poll_interval_seconds: int
    high_value_threshold: int


def load_config() -> Config:
    required = [
        "SF_USERNAME",
        "SF_CONSUMER_KEY",
        "SF_ALERT_OWNER_ID",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    return Config(
        sf_username=os.environ["SF_USERNAME"],
        sf_consumer_key=os.environ["SF_CONSUMER_KEY"],
        sf_private_key_file=os.getenv("SF_PRIVATE_KEY_FILE", "server.key"),
        sf_wealth_score_field=os.getenv("SF_WEALTH_SCORE_FIELD", "Wealth_Score__c"),
        sf_processed_field=os.getenv("SF_PROCESSED_FIELD", "Wealth_Scan_Processed__c"),
        sf_alert_owner_id=os.environ["SF_ALERT_OWNER_ID"],
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma4:e4b"),
        fec_api_key=os.getenv("FEC_API_KEY", ""),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        high_value_threshold=int(os.getenv("HIGH_VALUE_THRESHOLD", "80")),
    )
