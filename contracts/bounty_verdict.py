# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

import json
from dataclasses import dataclass

def _addr_str(a: Address) -> str:
    try:
        return a.as_hex
    except Exception:
        return str(a)

def _to_address(val) -> Address:
    if val is None:
        return Address("0x0000000000000000000000000000000000000000")
    if isinstance(val, Address):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str.startswith("0x"):
            val_str = "0x" + val_str
        return Address(val_str)
    return Address(val)

@allow_storage
@dataclass
class BountyReport:
    program_id: str
    reporter: Address
    affected_component: str   # vd "ERC20 token contract", "bridge module"
    vulnerability_type: str   # vd "Reentrancy", "Integer overflow", "Access control"
    description: str          # mo ta ky thuat (max 1000 ky tu)
    poc_url: str              # URL PoC: GitHub Gist, writeup, video demo
    additional_url: str       # URL bo sung (optional)
    status: str               # "SUBMITTED" | "EVALUATED"
    severity: str             # "CRITICAL"|"HIGH"|"MEDIUM"|"LOW"|"INVALID"|"INSUFFICIENT"
    in_scope: bool
    confidence: bigint
    reasoning: str
    paid_out: bool

class Contract(gl.Contract):
    reports: TreeMap[str, BountyReport]
    next_report_id: bigint
    registry_address: Address
    owner: Address

    def __init__(self):
        self.next_report_id = bigint(1)
        self.registry_address = Address("0x0000000000000000000000000000000000000000")
        self.owner = _to_address(gl.message.sender_address)

    @gl.public.write
    def set_registry(self, address: Address) -> None:
        sender = _to_address(gl.message.sender_address)
        if sender != self.owner:
            raise gl.vm.UserError("Unauthorized: caller is not contract owner")

        self.registry_address = _to_address(address)

    @gl.public.write
    def submit_report(
        self,
        program_id: str,
        affected_component: str,
        vulnerability_type: str,
        description: str,
        poc_url: str,
        additional_url: str
    ) -> str:
        reporter = _to_address(gl.message.sender_address)

        if self.registry_address == Address("0x0000000000000000000000000000000000000000"):
            raise gl.vm.UserError("Registry address not set")

        try:
            prog_json = gl.get_contract_at(self.registry_address).get_program(program_id)
            prog_data = json.loads(prog_json)
        except Exception as e:
            raise gl.vm.UserError("Program not found in registry")

        if prog_data.get("status") != "ACTIVE":
            raise gl.vm.UserError("Program is not active")

        if not affected_component or len(affected_component.strip()) == 0:
            raise gl.vm.UserError("Affected component cannot be empty")

        if not vulnerability_type or len(vulnerability_type.strip()) == 0:
            raise gl.vm.UserError("Vulnerability type cannot be empty")

        if not description or len(description.strip()) == 0 or len(description) > 1000:
            raise gl.vm.UserError("Invalid description: cannot be empty or exceed 1000 characters")

        if not poc_url or not (poc_url.startswith("http://") or poc_url.startswith("https://")):
            raise gl.vm.UserError("Invalid PoC URL: must start with http:// or https://")

        if additional_url != "":
            if not (additional_url.startswith("http://") or additional_url.startswith("https://")):
                raise gl.vm.UserError("Invalid additional URL: must start with http:// or https://")

        report_id = str(self.next_report_id)
        self.next_report_id += bigint(1)

        new_report = BountyReport(
            program_id=program_id,
            reporter=reporter,
            affected_component=affected_component.strip(),
            vulnerability_type=vulnerability_type.strip(),
            description=description.strip(),
            poc_url=poc_url.strip(),
            additional_url=additional_url.strip(),
            status="SUBMITTED",
            severity="",
            in_scope=False,
            confidence=bigint(0),
            reasoning="",
            paid_out=False
        )

        self.reports[report_id] = new_report
        return report_id

    @gl.public.write
    def evaluate_report(self, report_id: str) -> None:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")

        report = self.reports[report_id]
        if report.status == "EVALUATED":
            raise gl.vm.UserError("Report is already evaluated")

        # Fetch scope URL from BountyRegistry cross-contract call
        scope_url = ""
        try:
            prog_json = gl.get_contract_at(self.registry_address).get_program(report.program_id)
            prog_data = json.loads(prog_json)
            scope_url = prog_data.get("scope_url", "")
        except Exception as e:
            raise gl.vm.UserError(f"Failed to fetch program scope from registry: {str(e)}")

        poc_url = report.poc_url
        additional_url = report.additional_url
        affected_component = report.affected_component
        vulnerability_type = report.vulnerability_type
        description = report.description

        def leader_fn():
            # 1. Fetch PoC URL
            poc_content = ""
            try:
                res = gl.nondet.web.render(poc_url)
                body = res.body if hasattr(res, 'body') else str(res)
                poc_content = body[:4000] if body else "(empty PoC page)"
            except Exception as e:
                poc_content = f"(failed to fetch PoC: {str(e)})"

            # 2. Fetch Scope URL
            scope_content = ""
            try:
                res2 = gl.nondet.web.render(scope_url)
                body2 = res2.body if hasattr(res2, 'body') else str(res2)
                scope_content = body2[:3000] if body2 else "(empty scope page)"
            except Exception as e:
                scope_content = f"(failed to fetch scope: {str(e)})"

            # 3. Fetch Additional URL if present
            additional_content = ""
            if additional_url:
                try:
                    res3 = gl.nondet.web.render(additional_url)
                    body3 = res3.body if hasattr(res3, 'body') else str(res3)
                    additional_content = body3[:2000] if body3 else "(empty)"
                except Exception as e:
                    additional_content = f"(failed to fetch: {str(e)})"

            prompt = f"""You are an expert blockchain security auditor and bug bounty evaluator.

Protocol Bounty Scope Page:
{scope_content}

Vulnerability Report:
- Affected Component: "{affected_component}"
- Vulnerability Type: "{vulnerability_type}"
- Reporter Description: "{description}"

Proof of Concept (PoC) fetched on-chain:
{poc_content}

Additional Reference:
{additional_content if additional_content else "(none provided)"}

Your task:
1. Determine if the affected component is IN SCOPE based on the scope page.
2. Evaluate the severity of the vulnerability:
   - CRITICAL: funds at direct risk, full protocol compromise possible
   - HIGH: significant impact, partial fund loss or major functionality broken
   - MEDIUM: moderate impact, no direct fund loss but meaningful risk
   - LOW: minimal impact, best practice violation
   - INVALID: not a vulnerability, intended behavior, or out of scope
3. If the PoC is unavailable or insufficient to verify the claim, use INSUFFICIENT.
4. Rate confidence 0-100. Provide 2-3 sentence technical reasoning.

Return ONLY raw JSON, no markdown, no backticks:
{{"severity": "CRITICAL"|"HIGH"|"MEDIUM"|"LOW"|"INVALID"|"INSUFFICIENT",
  "in_scope": true|false,
  "confidence": <0-100>,
  "reasoning": "<technical explanation>"}}"""

            raw = gl.nondet.exec_prompt(prompt, response_format="json")

            try:
                if isinstance(raw, dict):
                    parsed = raw
                else:
                    cleaned = str(raw).strip()
                    if cleaned.startswith("```json"): cleaned = cleaned[7:]
                    if cleaned.startswith("```"): cleaned = cleaned[3:]
                    if cleaned.endswith("```"): cleaned = cleaned[:-3]
                    parsed = json.loads(cleaned.strip())

                severity = parsed.get("severity", "INSUFFICIENT")
                valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INVALID", "INSUFFICIENT"]
                if severity not in valid_severities:
                    severity = "INSUFFICIENT"

                in_scope = bool(parsed.get("in_scope", False))

                try:
                    conf = int(parsed.get("confidence", 0))
                    conf = max(0, min(100, conf))
                except:
                    conf = 0

                return {
                    "severity": severity,
                    "in_scope": in_scope,
                    "confidence": conf,
                    "reasoning": str(parsed.get("reasoning", ""))
                }
            except Exception as e:
                return {
                    "severity": "INSUFFICIENT",
                    "in_scope": False,
                    "confidence": 0,
                    "reasoning": f"Parse error: {str(e)}"
                }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            lp = leader_res.calldata
            if not isinstance(lp, dict):
                return False

            leader_severity = lp.get("severity")
            leader_scope = lp.get("in_scope")
            leader_conf = lp.get("confidence")

            valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INVALID", "INSUFFICIENT"]
            if leader_severity not in valid_severities:
                return False
            if not isinstance(leader_scope, bool):
                return False
            try:
                lc = int(leader_conf)
                if not (0 <= lc <= 100): return False
            except:
                return False

            try:
                my_result = leader_fn()
            except:
                return False

            if my_result.get("severity") != leader_severity:
                return False
            if my_result.get("in_scope") != leader_scope:
                return False

            try:
                mc = int(my_result.get("confidence", 0))
                if not (0 <= mc <= 100): return False
            except:
                return False

            def _band(c):
                if c < 35: return 1
                elif c < 80: return 2
                else: return 3

            return _band(mc) == _band(lc)

        ruling = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        severity = ruling["severity"]
        in_scope = ruling["in_scope"]
        confidence = ruling["confidence"]
        reasoning = ruling["reasoning"]

        report.severity = severity
        report.in_scope = in_scope
        report.confidence = bigint(confidence)
        report.reasoning = reasoning

        if severity == "INSUFFICIENT":
            report.paid_out = False
            report.status = "SUBMITTED"
        elif severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] and in_scope:
            gl.get_contract_at(self.registry_address).execute_payout(
                report.program_id,
                report.reporter,
                severity
            )
            report.paid_out = True
            report.status = "EVALUATED"
        else:
            report.paid_out = False
            report.status = "EVALUATED"

        self.reports[report_id] = report

    @gl.public.view
    def get_report(self, report_id: str) -> str:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")

        rep = self.reports[report_id]
        res = {
            "report_id": report_id,
            "program_id": rep.program_id,
            "reporter": _addr_str(rep.reporter),
            "affected_component": rep.affected_component,
            "vulnerability_type": rep.vulnerability_type,
            "description": rep.description,
            "poc_url": rep.poc_url,
            "additional_url": rep.additional_url,
            "status": rep.status,
            "severity": rep.severity,
            "in_scope": rep.in_scope,
            "confidence": int(rep.confidence),
            "reasoning": rep.reasoning,
            "paid_out": rep.paid_out
        }
        return json.dumps(res)

    @gl.public.view
    def list_reports(self, program_id: str, status_filter: str) -> str:
        if status_filter not in ["", "SUBMITTED", "EVALUATED"]:
            raise gl.vm.UserError("Invalid status filter")

        results = []
        limit = int(self.next_report_id)
        for i in range(1, limit):
            rid = str(i)
            if rid in self.reports:
                rep = self.reports[rid]
                matches_prog = (program_id == "" or rep.program_id == program_id)
                matches_stat = (status_filter == "" or rep.status == status_filter)
                if matches_prog and matches_stat:
                    results.append({
                        "report_id": rid,
                        "program_id": rep.program_id,
                        "reporter": _addr_str(rep.reporter),
                        "affected_component": rep.affected_component,
                        "vulnerability_type": rep.vulnerability_type,
                        "description": rep.description,
                        "poc_url": rep.poc_url,
                        "additional_url": rep.additional_url,
                        "status": rep.status,
                        "severity": rep.severity,
                        "in_scope": rep.in_scope,
                        "confidence": int(rep.confidence),
                        "reasoning": rep.reasoning,
                        "paid_out": rep.paid_out
                    })
        return json.dumps(results)

    @gl.public.view
    def get_report_count(self) -> int:
        return int(self.next_report_id) - 1
