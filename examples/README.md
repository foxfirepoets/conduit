# Conduit Examples

Demo agents that showcase Conduit's browser automation and cryptographic audit capabilities. These agents are designed to be listed on the [SwarmSync.ai](https://swarmsync.ai) marketplace.

## compliance_auditor.py

Automated website compliance checker that verifies common regulatory and best-practice requirements:

- **HTTPS enforcement** -- confirms the site is served over TLS
- **Privacy policy** -- searches for a privacy policy link or GDPR notice
- **Terms of service** -- searches for terms of use / terms and conditions
- **Cookie consent** -- detects cookie consent banners or notices
- **Contact information** -- looks for email addresses or "Contact Us" links

Every check is recorded in Conduit's SHA-256 hash-chained audit log. At the end of the audit, a self-verifiable proof bundle (`.tar.gz`) is exported that anyone can verify without installing Conduit.

### Usage

```bash
# Audit the default target (https://example.com)
python examples/compliance_auditor.py

# Audit a specific URL
python examples/compliance_auditor.py https://yoursite.com
```

### Output

The auditor produces three artifacts:

1. **Human-readable report** printed to stdout with pass/fail for each check and an overall score (0-100).
2. **JSON report** written to `~/.cato/proofs/report_<session_id>.json` for programmatic consumption.
3. **Proof bundle** written to `~/.cato/proofs/conduit_proof_<id>.tar.gz` -- extract and run `python verify.py` inside to verify the hash chain.

### SwarmSync Marketplace

This agent is listed on SwarmSync.ai at **$0.10 per audit** under the "Compliance & Legal" category. The proof bundle serves as a tamper-evident receipt for the buyer.

### Requirements

- Python 3.10+
- Conduit repository cloned (this file lives in `examples/`)
- Dependencies from `requirements.txt` installed (`pip install -r requirements.txt`)
- A Chromium-compatible browser available for Patchright (installed automatically on first run)

### Programmatic Usage

```python
import asyncio
from examples.compliance_auditor import run_compliance_audit

async def main():
    report = await run_compliance_audit(
        "https://example.com",
        session_id="my-custom-session",
        budget_cents=50,
    )
    print(f"Score: {report.overall_score}/100")
    print(f"Proof: {report.proof_bundle_path}")

asyncio.run(main())
```
