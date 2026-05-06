# Salesforce Donor Wealth Scoring Agent

Polls Salesforce for new Contact records, uses Claude AI to estimate a wealth score (0–100) from name, title, and location, writes the score back to the Contact, and creates a high-priority Task alert for contacts that score 80 or above.

---

## How it works

1. Every N seconds (default: 5 minutes), the agent queries Salesforce for Contacts where `Wealth_Scan_Processed__c` is false or null.
2. For each contact, Claude estimates a wealth score based on professional title and geographic location.
3. The score is written to `Wealth_Score__c` and `Wealth_Scan_Processed__c` is set to `true`.
4. If the score is ≥ `HIGH_VALUE_THRESHOLD` (default: 80) and no alert Task already exists, a Task is created on the Contact assigned to the configured Salesforce user.

---

## Salesforce Setup (required before first run)

### 1. Create custom fields on the Contact object

Go to **Setup > Object Manager > Contact > Fields & Relationships > New**

**Wealth Score field**
- Data Type: `Number`
- Field Label: `Wealth Score`
- Field Name: `Wealth_Score` → API name: `Wealth_Score__c`
- Length: 3, Decimal Places: 0

**Processed flag field**
- Data Type: `Checkbox`
- Field Label: `Wealth Scan Processed`
- Field Name: `Wealth_Scan_Processed` → API name: `Wealth_Scan_Processed__c`
- Default Value: `Unchecked`

### 2. Set field-level security

For both fields, edit Field-Level Security and grant **Read + Edit** to the profile used by your integration user.

### 3. Get your security token

If your org enforces IP restrictions: **Settings > Reset My Security Token** — Salesforce emails it to you.

### 4. Get the Alert Owner's User ID

**Setup > Users** → click the target user → copy the 18-character ID from the URL bar.

### 5. Verify API access

The integration user's profile must have **"API Enabled"** checked under System Permissions.

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SF_USERNAME` | Yes | — | Salesforce login email |
| `SF_PASSWORD` | Yes | — | Salesforce password |
| `SF_SECURITY_TOKEN` | Yes | — | Salesforce security token |
| `SF_DOMAIN` | No | `login` | Use `test` for sandbox orgs |
| `SF_WEALTH_SCORE_FIELD` | No | `Wealth_Score__c` | API name of the numeric score field |
| `SF_PROCESSED_FIELD` | No | `Wealth_Scan_Processed__c` | API name of the boolean processed flag |
| `SF_ALERT_OWNER_ID` | Yes | — | 18-char Salesforce User ID for Task assignment |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `POLL_INTERVAL_SECONDS` | No | `300` | Polling frequency in seconds |
| `HIGH_VALUE_THRESHOLD` | No | `80` | Minimum score to trigger a Task alert |

---

## Running

```bash
python main.py
```

The agent runs an immediate cycle on startup, then polls on the configured interval. Press `Ctrl+C` to stop.

---

## Re-scoring a contact

To re-run wealth scoring on a contact that has already been processed, clear the processed flag in Salesforce:
- Set `Wealth_Scan_Processed__c` back to `false` (unchecked) on the Contact record.
- The agent will pick it up on the next poll cycle and overwrite the existing score.
