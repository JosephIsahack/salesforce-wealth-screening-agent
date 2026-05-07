# Salesforce Wealth Screening Agent

Polls Salesforce for new Contact records, enriches each with data from free public APIs (FEC, SEC EDGAR, ProPublica), then uses a local LLM via Ollama to produce a 0–100 wealth score. High-scoring contacts automatically trigger a Task alert assigned to the designated Salesforce user. No paid AI API required.

---

## How it works

1. Every N seconds (default: 5 minutes), the agent queries Salesforce for Contacts where `Wealth_Scan_Processed__c` is false or null.
2. Each contact is enriched with public records signals:
   - **FEC** — federal campaign contribution history
   - **SEC EDGAR** — insider trading (Form 4) and executive compensation (DEF 14A) filings
   - **ProPublica** — IRS 990 foundation/nonprofit data
3. A local LLM (running via Ollama) synthesizes the contact fields and enrichment signals into a wealth score and a brief rationale.
4. The score is written to `Wealth_Score__c` and `Wealth_Scan_Processed__c` is set to `true`.
5. If the score is ≥ `HIGH_VALUE_THRESHOLD` (default: 80) and no alert Task already exists, a high-priority Task is created on the Contact assigned to the configured Salesforce user.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a model pulled (see below)
- Salesforce org with API access enabled

---

## Ollama setup

```bash
# Install Ollama
brew install ollama

# Pull a model (gemma4:e4b is the default — swap for any model you prefer)
ollama pull gemma4:e4b

# Start the Ollama server
ollama serve
```

Ollama must be running before starting the agent. On an M2 Mac with 24GB RAM, `gemma4:e4b` runs fast with Metal GPU acceleration.

---

## Salesforce setup (required before first run)

### 1. Create custom fields on the Contact object

Go to **Setup > Object Manager > Contact > Fields & Relationships > New**

**Wealth Score**
- Data Type: `Number`
- Field Label: `Wealth Score`
- Field Name: `Wealth_Score` → API name: `Wealth_Score__c`
- Length: 3, Decimal Places: 0

**Wealth Scan Processed**
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
pip3 install -r requirements.txt
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
| `OLLAMA_BASE_URL` | No | `http://localhost:11434/v1` | Ollama API endpoint |
| `OLLAMA_MODEL` | No | `gemma4:e4b` | Any model pulled in Ollama |
| `FEC_API_KEY` | No | `DEMO_KEY` | Free key at [api.data.gov](https://api.data.gov/signup/) for higher rate limits |
| `POLL_INTERVAL_SECONDS` | No | `300` | Polling frequency in seconds |
| `HIGH_VALUE_THRESHOLD` | No | `80` | Minimum score to trigger a Task alert |

---

## Running

```bash
python3 main.py
```

The agent runs an immediate cycle on startup, then polls on the configured interval. Press `Ctrl+C` to stop.

---

## Re-scoring a contact

Set `Wealth_Scan_Processed__c` back to `false` on the Contact record in Salesforce. The agent will pick it up on the next poll cycle and overwrite the existing score.
