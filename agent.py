from loguru import logger
from config import Config
from salesforce_client import SalesforceClient
from claude_client import ClaudeClient
from enrichment_client import EnrichmentClient


class WealthScoringAgent:
    def __init__(self, config: Config):
        self.config = config
        self.sf = SalesforceClient(config)
        self.claude = ClaudeClient(config)
        self.enrichment = EnrichmentClient(config)

    def run_cycle(self) -> None:
        """
        One full polling cycle:
        1. Fetch unprocessed Contacts from Salesforce
        2. Score each via Claude
        3. Write score + processed flag back to Salesforce
        4. Create a high-priority Task if score >= threshold and no Task exists yet
        """
        logger.info("Starting poll cycle")

        try:
            contacts = self.sf.get_unprocessed_contacts()
        except Exception as e:
            logger.error(f"Failed to fetch contacts from Salesforce: {e}")
            return

        logger.info(f"Found {len(contacts)} unprocessed contact(s)")

        for contact in contacts:
            contact_id = contact["Id"]
            name = f"{contact.get('FirstName') or ''} {contact.get('LastName') or ''}".strip()

            try:
                enrichment = self.enrichment.enrich(contact)
                if enrichment:
                    sources = [s for s in ("fec", "sec_edgar", "propublica") if enrichment.get(s, {}).get("found")]
                    logger.debug(f"Enrichment signals for {name}: {sources or 'none found'}")

                score, reasoning = self.claude.estimate_wealth_score(contact, enrichment)
                logger.info(f"Contact {contact_id} ({name}) scored {score}/100")

                self.sf.update_contact_score(contact_id, score)

                if score >= self.config.high_value_threshold:
                    if not self.config.sf_alert_owner_id:
                        logger.info(f"High-value contact: {name} (score {score}) — no SF_ALERT_OWNER_ID set, skipping Task")
                    elif not self.sf.task_exists_for_contact(contact_id):
                        self.sf.create_alert_task(contact, score, reasoning)
                        logger.info(f"Alert Task created for {name} (score {score})")
                    else:
                        logger.debug(f"Alert Task already exists for {name}, skipping")

            except Exception as e:
                logger.error(f"Error processing contact {contact_id} ({name}): {e}")

        logger.info("Poll cycle complete")
