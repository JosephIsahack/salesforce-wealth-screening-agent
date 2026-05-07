"""
Quick connectivity test — verifies JWT auth and returns unprocessed contact count.
Run: python3 test_salesforce.py
"""
from config import load_config
from salesforce_client import SalesforceClient

print("Loading config...")
config = load_config()

print(f"Connecting to Salesforce as {config.sf_username}...")
sf = SalesforceClient(config)

print("Querying unprocessed contacts...")
contacts = sf.get_unprocessed_contacts()

print(f"\n✓ Connected successfully.")
print(f"  Unprocessed contacts ready to score: {len(contacts)}")

if contacts:
    first = contacts[0]
    name = f"{first.get('FirstName') or ''} {first.get('LastName') or ''}".strip()
    print(f"  First contact in queue: {name} (ID: {first['Id']})")
