import pytest
import json
import pathlib
import gltest.direct as direct

CONTRACTS_DIR = pathlib.Path(__file__).parent.parent / "contracts"
REGISTRY_PATH = CONTRACTS_DIR / "bounty_registry.py"
VERDICT_PATH = CONTRACTS_DIR / "bounty_verdict.py"


def setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob):
    # Deploy BountyRegistry with Alice as owner
    with direct_vm.prank(direct_alice):
        registry = direct_deploy(REGISTRY_PATH)

    # Deploy BountyVerdict with Alice as owner
    with direct_vm.prank(direct_alice):
        verdict = direct_deploy(VERDICT_PATH)

    # Link cross-contract addresses
    with direct_vm.prank(direct_alice):
        registry.set_verdict_contract(verdict.address)
        verdict.set_registry(registry.address)

    # Create program 1 by Bob (protocol operator)
    with direct_vm.prank(direct_bob):
        prog_id = registry.create_program(
            "DeFi Protocol",
            "https://example.com/bounty-scope",
            1000, # Critical
            500,  # High
            200,  # Medium
            50    # Low
        )

    # Deposit 3000 GEN escrow into program 1 by Bob
    direct_vm.deal(direct_bob, 10000)
    with direct_vm.prank(direct_bob):
        direct_vm._value = 3000
        registry.deposit_escrow(prog_id)
        direct_vm._value = 0

    return registry, verdict, prog_id


def test_critical_payout(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    # Submit report by Charlie
    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "ERC20 Token Vault",
            "Reentrancy",
            "Reentrancy flaw allows draining vault reserves in single transaction",
            "https://gist.github.com/poc-critical",
            ""
        )

    # Mocks for web render & LLM
    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: ERC20 Token Vault and core smart contracts.")
    direct_vm.mock_web("https://gist.github.com/poc-critical", "PoC code: function drain() { vault.withdraw(); }")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "CRITICAL",
            "in_scope": True,
            "confidence": 95,
            "reasoning": "Confirmed reentrancy vulnerability leading to complete fund drain of the token vault."
        })
    )

    # Evaluate report
    verdict.evaluate_report(report_id)

    rep_json = verdict.get_report(report_id)
    rep = json.loads(rep_json)

    assert rep["status"] == "EVALUATED"
    assert rep["severity"] == "CRITICAL"
    assert rep["in_scope"] is True
    assert rep["confidence"] == 95
    assert rep["paid_out"] is True

    prog = json.loads(registry.get_program(prog_id))
    assert prog["total_paid_out"] == 1000


def test_high_payout(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Bridge Module",
            "Integer Overflow",
            "Overflow in token calculation causes improper balance update",
            "https://gist.github.com/poc-high",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: Bridge Module contracts.")
    direct_vm.mock_web("https://gist.github.com/poc-high", "PoC showing overflow in bridge transfer calculations.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "HIGH",
            "in_scope": True,
            "confidence": 85,
            "reasoning": "Integer overflow allows unauthorized minting of partial bridge tokens."
        })
    )

    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    assert rep["status"] == "EVALUATED"
    assert rep["severity"] == "HIGH"
    assert rep["in_scope"] is True
    assert rep["paid_out"] is True

    prog = json.loads(registry.get_program(prog_id))
    assert prog["total_paid_out"] == 500


def test_invalid_no_payout(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Staking Contract",
            "Phishing",
            "Social engineering claim on protocol frontend",
            "https://gist.github.com/poc-invalid",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: Staking Contract on-chain code.")
    direct_vm.mock_web("https://gist.github.com/poc-invalid", "Description of off-chain phishing email.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "INVALID",
            "in_scope": False,
            "confidence": 90,
            "reasoning": "Social engineering and email phishing are outside the technical smart contract scope."
        })
    )

    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    assert rep["status"] == "EVALUATED"
    assert rep["severity"] == "INVALID"
    assert rep["paid_out"] is False

    prog = json.loads(registry.get_program(prog_id))
    assert prog["total_paid_out"] == 0


def test_out_of_scope_no_payout(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Deprecated V1 Router",
            "Access Control",
            "Missing owner modifier in legacy V1 contract",
            "https://gist.github.com/poc-v1",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: Only V2 Router contracts. V1 is deprecated and out of scope.")
    direct_vm.mock_web("https://gist.github.com/poc-v1", "PoC for V1 router access control bypass.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "HIGH",
            "in_scope": False,
            "confidence": 88,
            "reasoning": "High severity flaw identified, but V1 router is explicitly listed as out of scope on protocol scope page."
        })
    )

    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    assert rep["status"] == "EVALUATED"
    assert rep["severity"] == "HIGH"
    assert rep["in_scope"] is False
    assert rep["paid_out"] is False

    prog = json.loads(registry.get_program(prog_id))
    assert prog["total_paid_out"] == 0


def test_insufficient_resubmit(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Governance Contract",
            "Logic Error",
            "Vague statement about proposal voting without clear proof",
            "https://gist.github.com/poc-vague",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: Governance contracts.")
    direct_vm.mock_web("https://gist.github.com/poc-vague", "Empty text file without code.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "INSUFFICIENT",
            "in_scope": True,
            "confidence": 20,
            "reasoning": "Submitted PoC page is empty. Cannot verify vulnerability claim."
        })
    )

    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    # Status remains SUBMITTED so reporter can update/resubmit
    assert rep["status"] == "SUBMITTED"
    assert rep["severity"] == "INSUFFICIENT"
    assert rep["paid_out"] is False


def test_insufficient_out_of_scope_resubmit(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Unknown Module",
            "Logic Error",
            "Insufficient evidence provided",
            "https://gist.github.com/poc-insufficient-oos",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "Scope page.")
    direct_vm.mock_web("https://gist.github.com/poc-insufficient-oos", "Empty or broken page.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "INSUFFICIENT",
            "in_scope": False,  # INSUFFICIENT with in_scope == False MUST still remain retryable!
            "confidence": 15,
            "reasoning": "PoC page returned 404. Insufficient data."
        })
    )

    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    # Crucial steward requirement: EVERY INSUFFICIENT ruling remains retryable (status == SUBMITTED) regardless of in_scope flag
    assert rep["status"] == "SUBMITTED"
    assert rep["severity"] == "INSUFFICIENT"
    assert rep["paid_out"] is False


def test_empty_poc_url(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        with pytest.raises(Exception, match="Invalid PoC URL"):
            verdict.submit_report(
                prog_id,
                "Vault",
                "Reentrancy",
                "Description of bug",
                "",  # empty PoC URL
                ""
            )


def test_invalid_url_format(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        with pytest.raises(Exception, match="must start with http:// or https://"):
            verdict.submit_report(
                prog_id,
                "Vault",
                "Reentrancy",
                "Description of bug",
                "ftp://invalid-url-format.com",
                ""
            )


def test_program_not_active(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    # Bob pauses program 1
    with direct_vm.prank(direct_bob):
        registry.pause_program(prog_id)

    # Charlie tries submitting report to paused program
    with direct_vm.prank(direct_charlie):
        with pytest.raises(Exception, match="Program is not active"):
            verdict.submit_report(
                prog_id,
                "Vault",
                "Reentrancy",
                "Description of bug",
                "https://gist.github.com/poc-test",
                ""
            )


def test_evaluate_already_evaluated(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Vault",
            "Reentrancy",
            "Reentrancy bug in deposit function",
            "https://gist.github.com/poc-eval",
            ""
        )

    direct_vm.mock_web("https://example.com/bounty-scope", "Vault contract scope.")
    direct_vm.mock_web("https://gist.github.com/poc-eval", "PoC details.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "MEDIUM",
            "in_scope": True,
            "confidence": 75,
            "reasoning": "Moderate impact reentrancy flaw."
        })
    )

    verdict.evaluate_report(report_id)

    # Second evaluation attempt must raise UserError
    with pytest.raises(Exception, match="Report is already evaluated"):
        verdict.evaluate_report(report_id)


def test_web_render_fail(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    with direct_vm.prank(direct_charlie):
        report_id = verdict.submit_report(
            prog_id,
            "Vault",
            "Reentrancy",
            "Detailed explanation of reentrancy in withdraw function",
            "https://offline-site.com/poc",
            ""
        )

    # Intentionally do NOT mock web render for https://offline-site.com/poc so web.render raises exception
    direct_vm.mock_web("https://example.com/bounty-scope", "In Scope: Vault contract.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "LOW",
            "in_scope": True,
            "confidence": 60,
            "reasoning": "Evaluated based on detailed technical report description despite PoC site connection error."
        })
    )

    # Contract must handle web render failure gracefully without VM crash
    verdict.evaluate_report(report_id)

    rep = json.loads(verdict.get_report(report_id))
    assert rep["status"] == "EVALUATED"
    assert rep["severity"] == "LOW"


def test_double_payout_protection(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    # Unauthorized external account (Bob or Charlie) calls execute_payout directly on BountyRegistry
    with direct_vm.prank(direct_bob):
        with pytest.raises(Exception, match="Only verdict contract can trigger payout"):
            registry.execute_payout(prog_id, direct_charlie, "CRITICAL")


def test_list_reports_filter(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    registry, verdict, prog_id = setup_contracts(direct_deploy, direct_vm, direct_alice, direct_bob)

    # Report 1
    with direct_vm.prank(direct_charlie):
        r1 = verdict.submit_report(
            prog_id,
            "Component A",
            "Reentrancy",
            "Description 1",
            "https://gist.github.com/poc-1",
            ""
        )

    # Report 2
    with direct_vm.prank(direct_charlie):
        r2 = verdict.submit_report(
            prog_id,
            "Component B",
            "Access Control",
            "Description 2",
            "https://gist.github.com/poc-2",
            ""
        )

    # Evaluate Report 1
    direct_vm.mock_web("https://example.com/bounty-scope", "Scope page.")
    direct_vm.mock_web("https://gist.github.com/poc-1", "PoC 1.")
    direct_vm.mock_llm(
        "expert blockchain security auditor",
        json.dumps({
            "severity": "LOW",
            "in_scope": True,
            "confidence": 70,
            "reasoning": "Low severity vulnerability."
        })
    )
    verdict.evaluate_report(r1)

    # List SUBMITTED
    submitted_reports = json.loads(verdict.list_reports(prog_id, "SUBMITTED"))
    assert len(submitted_reports) == 1
    assert submitted_reports[0]["report_id"] == r2

    # List EVALUATED
    evaluated_reports = json.loads(verdict.list_reports(prog_id, "EVALUATED"))
    assert len(evaluated_reports) == 1
    assert evaluated_reports[0]["report_id"] == r1

    # List ALL
    all_reports = json.loads(verdict.list_reports(prog_id, ""))
    assert len(all_reports) == 2
