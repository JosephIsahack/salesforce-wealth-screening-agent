import json
import anthropic
from config import Config


class ClaudeClient:
    def __init__(self, config: Config):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def estimate_wealth_score(self, contact: dict, enrichment: dict | None = None) -> tuple[int, str]:
        """
        Ask Claude to estimate a wealth score (0-100) from contact fields and
        any enrichment signals gathered from public APIs (FEC, EDGAR, ProPublica).
        Returns (score, reasoning).
        """
        first = contact.get("FirstName") or ""
        last = contact.get("LastName") or ""
        title = contact.get("Title") or "Unknown"
        city = contact.get("MailingCity") or "Unknown"
        state = contact.get("MailingState") or "Unknown"
        zipcode = contact.get("MailingPostalCode") or "Unknown"

        enrichment_section = _format_enrichment(enrichment or {})

        prompt = f"""You are a wealth estimation assistant helping a nonprofit identify high-value donor prospects.

Based on the contact attributes and any public records data below, estimate a wealth score from 0 to 100.
0 = very low estimated net worth / giving capacity.
100 = very high estimated net worth / giving capacity.

CONTACT INFORMATION:
- Full Name: {first} {last}
- Professional Title: {title}
- Location: {city}, {state} {zipcode}
{enrichment_section}
Respond ONLY in this exact JSON format with no other text:
{{"score": <integer 0-100>, "reasoning": "<two or three sentences covering the strongest signals>"}}

Scoring guidance:
- Senior executive or C-suite titles (CEO, CFO, President, Partner, Founder) suggest higher wealth
- Geographic location (high cost-of-living metro areas, affluent zip codes) is a mild positive signal
- Generic or entry-level titles (Coordinator, Associate, Student) suggest lower capacity
- FEC contributions are a strong wealth signal — large total amounts (>$10k) significantly raise the score
- EDGAR filings (Form 4, SC 13G) indicate stock ownership or insider status at public companies — major signal
- A named family foundation in ProPublica is a very strong philanthropic capacity signal
- Public records data may match other people with the same name — weight it as supporting evidence, not proof
- Missing data should pull the score toward the median (50)"""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        parsed = json.loads(raw)
        score = max(0, min(100, int(parsed["score"])))
        reasoning = parsed["reasoning"]

        return score, reasoning


def _format_enrichment(enrichment: dict) -> str:
    """Render enrichment signals as a readable prompt section. Returns empty string if no signals found."""
    lines = []

    fec = enrichment.get("fec", {})
    if fec.get("fec_found"):
        recency = fec.get("fec_recency_score", 0)
        recency_label = "recent" if recency >= 0.7 else ("moderate" if recency >= 0.4 else "older")
        lines.append(
            f"- FEC campaign contributions: ${fec['fec_total_donated']:,.2f} total "
            f"across {fec['fec_num_donations']} donation(s), most recent {fec.get('fec_most_recent_year')} ({recency_label})"
        )
        if fec.get("fec_employers"):
            lines.append(f"  Employer(s) on FEC record: {fec['fec_employers']}")

    sec = enrichment.get("sec_edgar", {})
    if sec.get("sec_found"):
        roles = []
        if sec.get("sec_is_insider"):
            roles.append("stock insider (Form 4)")
        if sec.get("sec_is_executive"):
            roles.append("named executive (DEF 14A)")
        lines.append(
            f"- SEC EDGAR: {sec['sec_filing_count']} filing(s) — {', '.join(roles) or 'filing match'}"
            + (f", most recent {sec['sec_most_recent_filing']}" if sec.get("sec_most_recent_filing") else "")
        )
        if sec.get("sec_companies"):
            lines.append(f"  Associated company/companies: {sec['sec_companies']}")

    pp = enrichment.get("propublica", {})
    if pp.get("pp_found"):
        lines.append(
            f"- ProPublica / IRS 990: {pp['pp_num_orgs']} associated nonprofit(s): {pp['pp_org_names']}"
        )
        if pp.get("pp_largest_org_assets", 0) > 0:
            lines.append(f"  Largest org total assets: ${pp['pp_largest_org_assets']:,.0f}")

    if not lines:
        return ""

    return "\nPUBLIC RECORDS SIGNALS (note: name-based matches may include other individuals):\n" + "\n".join(lines) + "\n"
