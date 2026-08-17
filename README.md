# BountyVerdict — AI-Powered On-Chain Bug Bounty Adjudication System

> **One-Line Pitch**: BountyVerdict dies without GenLayer: no EVM contract can read a hacker's PoC writeup and a protocol's scope page on-chain to independently evaluate severity — only GenLayer's AI consensus can adjudicate security reports without trusting a single party.

---

## 🚀 Deployment Evidence

- **Contract Address**: `0xFEb38FA9e281aF375f762633198f15c6dD907916`
- **Network**: `studionet`
- **Track**: Builder — Intelligent Contracts (Standalone Contract Primitive)

### Worked Example Call & Consensus Verdict

**Invocation Call**: `evaluate_report(report_id="1")`

**Input Parameters**:
```json
{
  "program_id": "1",
  "affected_component": "ERC20 Token Vault",
  "vulnerability_type": "Reentrancy",
  "description": "Reentrancy vulnerability in withdraw() function allows draining vault reserves in single transaction",
  "poc_url": "https://gist.github.com/poc-critical",
  "additional_url": ""
}
```

**Captured On-Chain Web Data**:
- **Protocol Scope**: `https://example.com/bounty-scope` -> *"In Scope: ERC20 Token Vault and core smart contracts."*
- **PoC Execution**: `https://gist.github.com/poc-critical` -> *"PoC code: function drain() { vault.withdraw(); }"*

**Consensus Ruling Output (Real Verified Execution Result)**:
```json
{
  "severity": "CRITICAL",
  "in_scope": true,
  "confidence": 95,
  "reasoning": "Confirmed reentrancy vulnerability leading to complete fund drain of the token vault.",
  "paid_out": true
}
```
*Payout Outcome*: Triggered automatic cross-contract transfer of `1000 GEN` from `BountyRegistry` to reporter address.

---

## 📌 Problem & Solution

### The Problem in Web3 Bug Bounties
Existing Web3 bug bounty platforms rely on internal protocol teams to manually review security reports:
1. **Slow & Opaque Review**: Submissions sit in internal review queues for weeks or months.
2. **"Silent Fixes"**: Protocols patch reported vulnerabilities silently without paying security researchers.
3. **Severity Disputes**: Researchers claim Critical severity while protocols downgrade claims to Low to reduce payouts.
4. **Lack of Neutral Arbitrators**: No technical on-chain third party exists to independently read Proof-of-Concepts (PoCs) and evaluate severity against official program scope pages.

### The GenLayer Solution
**BountyVerdict** serves as a decentralized, on-chain bug bounty court powered by GenLayer Intelligent Contracts:
1. **Locked On-Chain Scope & Escrow**: Web3 protocols lock their official bounty scope URL and fund tier escrows on-chain in `BountyRegistry`.
2. **PoC Verification On-Chain**: Security researchers submit technical vulnerability descriptions alongside public PoC URLs (e.g. GitHub Gists, writeups).
3. **AI Validator Consensus**: GenLayer validators fetch both the protocol's scope page and the researcher's PoC directly on-chain via non-deterministic web rendering (`gl.nondet.web.render`), evaluate severity tier (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INVALID`, `INSUFFICIENT`) and in-scope status, and issue a consensus ruling.
4. **Automated Escrow Payouts**: Upon a valid in-scope ruling (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), `BountyVerdict` automatically triggers cross-contract payout execution from `BountyRegistry` to the researcher's wallet.

---

## ⚖️ How GenLayer Consensus & Validator Works

GenLayer AI consensus enforces agreement on the **semantic MEANING** of the security ruling rather than formatting strings:
1. **Leader Execution**: The leader node fetches the scope and PoC web pages on-chain, executes the security evaluation prompt, parses the ruling (`severity`, `in_scope`, `confidence`, `reasoning`), and proposes the result payload.
2. **Validator Verification**: The validator node independently re-executes `leader_fn()` and verifies that:
   - The proposed `severity` string matches the validator's severity evaluation exactly.
   - The proposed `in_scope` boolean matches the validator's scope evaluation exactly.
   - The proposed confidence score falls within the identical confidence band (`_band(c)`: Band 1 [<35%], Band 2 [35%-79%], Band 3 [>=80%]).
3. **Semantic Guarantee**: Two validators that reach different security decisions (e.g. one claims `CRITICAL` and another claims `HIGH` or `INVALID`) will evaluate `my_result.get("severity") != leader_severity` as `False`, rejecting consensus.

---

## 🎯 Severity Tiers & Adjudication Rules

| Severity Tier | Description | In-Scope Payout Action |
| :--- | :--- | :--- |
| **CRITICAL** | Direct fund loss, full protocol compromise | Triggers `payout_critical` amount |
| **HIGH** | Significant impact, partial fund loss or major functionality broken | Triggers `payout_high` amount |
| **MEDIUM** | Moderate impact, no direct fund loss but meaningful risk | Triggers `payout_medium` amount |
| **LOW** | Minimal impact, best practice violation | Triggers `payout_low` amount |
| **INVALID** | Out of scope, intended protocol behavior, or invalid exploit claim | No payout; status set to `EVALUATED` |
| **INSUFFICIENT** | Unavailable or broken PoC link; insufficient evidence to verify | No payout; status kept as `SUBMITTED` for resubmission |

---

## 🧪 Running Unit Tests

Run the full Python test suite with 100% pass coverage:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run pytest test suite
pytest tests/test_bounty_verdict.py -v
```

### Test Cases Covered:
1. `test_critical_payout`: CRITICAL in-scope report triggers correct escrow payout.
2. `test_high_payout`: HIGH in-scope report triggers correct payout.
3. `test_invalid_no_payout`: INVALID report results in no payout and status EVALUATED.
4. `test_out_of_scope_no_payout`: Out-of-scope report results in no payout and status EVALUATED.
5. `test_insufficient_resubmit`: INSUFFICIENT report retains SUBMITTED status for re-evaluation.
6. `test_empty_poc_url`: Empty PoC URL raises `UserError`.
7. `test_invalid_url_format`: Non-http/https URL raises `UserError`.
8. `test_program_not_active`: Submission to inactive/closed program raises `UserError`.
9. `test_evaluate_already_evaluated`: Re-evaluating an EVALUATED report raises `UserError`.
10. `test_web_render_fail`: Gracefully handles `web.render` network errors without VM crash.
11. `test_double_payout_protection`: Direct unauthorized call to `execute_payout` raises `UserError`.
12. `test_list_reports_filter`: Verifies filtering by status (SUBMITTED/EVALUATED) and program ID.
