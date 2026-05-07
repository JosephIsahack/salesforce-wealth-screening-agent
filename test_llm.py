import os
os.environ.update({
    "SF_USERNAME": "x", "SF_PASSWORD": "x",
    "SF_SECURITY_TOKEN": "x", "SF_ALERT_OWNER_ID": "x"
})

from config import load_config
from claude_client import ClaudeClient

config = load_config()
client = ClaudeClient(config)

print("Testing low-signal contact...")
score1, reason1 = client.estimate_wealth_score(
    {"FirstName": "Jane", "LastName": "Smith", "Title": "Coordinator",
     "MailingCity": "Cleveland", "MailingState": "OH", "MailingPostalCode": "44101"}
)
print(f"Score: {score1}/100")
print(f"Reasoning: {reason1}")

print()
print("Testing high-signal contact...")
score2, reason2 = client.estimate_wealth_score(
    {"FirstName": "James", "LastName": "Reynolds", "Title": "Managing Partner",
     "MailingCity": "Greenwich", "MailingState": "CT", "MailingPostalCode": "06830"},
    enrichment={
        "fec": {"fec_found": True, "fec_total_donated": 45000.0,
                "fec_num_donations": 12, "fec_most_recent_year": 2024,
                "fec_recency_score": 1.0, "fec_employers": "Reynolds Capital"},
        "sec_edgar": {"sec_found": True, "sec_is_insider": True,
                      "sec_is_executive": True, "sec_filing_count": 5,
                      "sec_companies": "Reynolds Capital Group",
                      "sec_most_recent_filing": "2024-03-01"},
        "propublica": {"pp_found": False}
    }
)
print(f"Score: {score2}/100")
print(f"Reasoning: {reason2}")
