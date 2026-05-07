import datetime
import requests
import jwt
from simple_salesforce import Salesforce
from config import Config

TOKEN_ENDPOINT = "https://login.salesforce.com/services/oauth2/token"


def _get_access_token(consumer_key: str, username: str, private_key_file: str) -> tuple[str, str]:
    """Exchange a JWT assertion for a Salesforce access token via Bearer Flow.
    Returns (access_token, instance_url).
    """
    with open(private_key_file, "r") as f:
        private_key = f.read()

    claim = {
        "iss": consumer_key,
        "sub": username,
        "aud": "https://login.salesforce.com",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5),
    }
    assertion = jwt.encode(claim, private_key, algorithm="RS256")

    resp = requests.post(TOKEN_ENDPOINT, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }, timeout=30)

    if not resp.ok:
        raise RuntimeError(f"Salesforce JWT auth failed: {resp.status_code} {resp.text[:200]}")

    data = resp.json()
    return data["access_token"], data["instance_url"]


class SalesforceClient:
    def __init__(self, config: Config):
        self.config = config
        access_token, instance_url = _get_access_token(
            config.sf_consumer_key,
            config.sf_username,
            config.sf_private_key_file,
        )
        self.sf = Salesforce(instance_url=instance_url, session_id=access_token)

    def get_unprocessed_contacts(self) -> list[dict]:
        """Return up to 200 Contacts where the processed flag is false or null."""
        pf = self.config.sf_processed_field
        query = f"""
            SELECT Id, FirstName, LastName, Title,
                   MailingCity, MailingState, MailingPostalCode
            FROM Contact
            WHERE {pf} = false
               OR {pf} = null
            ORDER BY CreatedDate ASC
            LIMIT 200
        """
        result = self.sf.query_all(query)
        return result["records"]

    def update_contact_score(self, contact_id: str, score: int) -> None:
        """Write the wealth score and mark the contact as processed in one call."""
        self.sf.Contact.update(contact_id, {
            self.config.sf_wealth_score_field: score,
            self.config.sf_processed_field: True,
        })

    def task_exists_for_contact(self, contact_id: str) -> bool:
        """Return True if a High-Value Donor Alert Task already exists for this Contact."""
        result = self.sf.query(
            f"SELECT Id FROM Task "
            f"WHERE WhoId = '{contact_id}' "
            f"AND Subject = 'High-Value Donor Alert' "
            f"LIMIT 1"
        )
        return result["totalSize"] > 0

    def create_alert_task(self, contact: dict, score: int, reasoning: str) -> None:
        """Create a high-priority Task on the Contact assigned to the alert owner."""
        contact_id = contact["Id"]
        name = f"{contact.get('FirstName') or ''} {contact.get('LastName') or ''}".strip()

        self.sf.Task.create({
            "Subject": "High-Value Donor Alert",
            "WhoId": contact_id,
            "OwnerId": self.config.sf_alert_owner_id,
            "Status": "Not Started",
            "Priority": "High",
            "Description": (
                f"Contact: {name}\n"
                f"Wealth Score: {score}/100\n\n"
                f"Scoring Rationale:\n{reasoning}\n\n"
                f"Generated automatically by the Wealth Scoring Agent."
            ),
        })
