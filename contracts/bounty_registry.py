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
class BountyProgram:
    protocol_name: str
    operator: Address
    scope_url: str           # URL trang bounty chinh thuc (in-scope assets)
    payout_critical: bigint  # GEN escrow cho Critical
    payout_high: bigint
    payout_medium: bigint
    payout_low: bigint
    status: str              # "ACTIVE" | "PAUSED" | "CLOSED"
    total_deposited: bigint
    total_paid_out: bigint

class Contract(gl.Contract):
    programs: TreeMap[str, BountyProgram]
    next_program_id: bigint
    verdict_contract: Address   # dia chi BountyVerdict contract
    owner: Address

    def __init__(self):
        self.next_program_id = bigint(1)
        self.owner = _to_address(gl.message.sender_address)
        self.verdict_contract = Address("0x0000000000000000000000000000000000000000")

    @gl.public.write
    def create_program(
        self,
        protocol_name: str,
        scope_url: str,
        payout_critical: int,
        payout_high: int,
        payout_medium: int,
        payout_low: int
    ) -> str:
        operator = _to_address(gl.message.sender_address)

        if not protocol_name or len(protocol_name.strip()) == 0 or len(protocol_name) > 100:
            raise gl.vm.UserError("Invalid protocol name: cannot be empty or exceed 100 characters")

        if not scope_url or not (scope_url.startswith("http://") or scope_url.startswith("https://")):
            raise gl.vm.UserError("Invalid scope URL: must start with http:// or https://")

        pc = bigint(payout_critical)
        ph = bigint(payout_high)
        pm = bigint(payout_medium)
        pl = bigint(payout_low)

        if not (pc > ph and ph > pm and pm > pl and pl > bigint(0)):
            raise gl.vm.UserError("Invalid payout hierarchy: payout_critical > payout_high > payout_medium > payout_low > 0")

        program_id = str(self.next_program_id)
        self.next_program_id += bigint(1)

        new_program = BountyProgram(
            protocol_name=protocol_name.strip(),
            operator=operator,
            scope_url=scope_url.strip(),
            payout_critical=pc,
            payout_high=ph,
            payout_medium=pm,
            payout_low=pl,
            status="ACTIVE",
            total_deposited=bigint(0),
            total_paid_out=bigint(0)
        )

        self.programs[program_id] = new_program
        return program_id

    @gl.public.write
    def deposit_escrow(self, program_id: str) -> None:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        program = self.programs[program_id]
        sender = _to_address(gl.message.sender_address)

        if sender != program.operator:
            raise gl.vm.UserError("Unauthorized: caller is not program operator")

        val = gl.message.value
        if val <= 0:
            raise gl.vm.UserError("Must deposit value greater than 0")

        program.total_deposited += bigint(val)
        self.programs[program_id] = program

    @gl.public.write
    def set_verdict_contract(self, address: Address) -> None:
        sender = _to_address(gl.message.sender_address)
        if sender != self.owner:
            raise gl.vm.UserError("Unauthorized: caller is not contract owner")

        self.verdict_contract = _to_address(address)

    @gl.public.write
    def pause_program(self, program_id: str) -> None:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        program = self.programs[program_id]
        sender = _to_address(gl.message.sender_address)

        if sender != program.operator and sender != self.owner:
            raise gl.vm.UserError("Unauthorized: caller is not operator or owner")

        program.status = "PAUSED"
        self.programs[program_id] = program

    @gl.public.write
    def resume_program(self, program_id: str) -> None:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        program = self.programs[program_id]
        sender = _to_address(gl.message.sender_address)

        if sender != program.operator and sender != self.owner:
            raise gl.vm.UserError("Unauthorized: caller is not operator or owner")

        program.status = "ACTIVE"
        self.programs[program_id] = program

    @gl.public.write
    def execute_payout(self, program_id: str, recipient: Address, severity: str) -> None:
        sender = _to_address(gl.message.sender_address)
        if sender != self.verdict_contract:
            raise gl.vm.UserError("Only verdict contract can trigger payout")

        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        program = self.programs[program_id]

        amount = bigint(0)
        if severity == "CRITICAL":
            amount = program.payout_critical
        elif severity == "HIGH":
            amount = program.payout_high
        elif severity == "MEDIUM":
            amount = program.payout_medium
        elif severity == "LOW":
            amount = program.payout_low
        else:
            raise gl.vm.UserError("Invalid severity for payout")

        available_escrow = program.total_deposited - program.total_paid_out
        if available_escrow < amount:
            raise gl.vm.UserError("Insufficient escrow balance in program")

        rec_addr = _to_address(recipient)
        gl.get_contract_at(rec_addr).emit_transfer(value=u256(amount))

        program.total_paid_out += amount
        self.programs[program_id] = program

    @gl.public.view
    def get_program(self, program_id: str) -> str:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        p = self.programs[program_id]
        res = {
            "program_id": program_id,
            "protocol_name": p.protocol_name,
            "operator": _addr_str(p.operator),
            "scope_url": p.scope_url,
            "payout_critical": int(p.payout_critical),
            "payout_high": int(p.payout_high),
            "payout_medium": int(p.payout_medium),
            "payout_low": int(p.payout_low),
            "status": p.status,
            "total_deposited": int(p.total_deposited),
            "total_paid_out": int(p.total_paid_out)
        }
        return json.dumps(res)

    @gl.public.view
    def list_programs(self, status_filter: str) -> str:
        if status_filter not in ["", "ACTIVE", "PAUSED", "CLOSED"]:
            raise gl.vm.UserError("Invalid status filter")

        results = []
        limit = int(self.next_program_id)
        for i in range(1, limit):
            pid = str(i)
            if pid in self.programs:
                p = self.programs[pid]
                if status_filter == "" or p.status == status_filter:
                    results.append({
                        "program_id": pid,
                        "protocol_name": p.protocol_name,
                        "operator": _addr_str(p.operator),
                        "scope_url": p.scope_url,
                        "payout_critical": int(p.payout_critical),
                        "payout_high": int(p.payout_high),
                        "payout_medium": int(p.payout_medium),
                        "payout_low": int(p.payout_low),
                        "status": p.status,
                        "total_deposited": int(p.total_deposited),
                        "total_paid_out": int(p.total_paid_out)
                    })
        return json.dumps(results)

    @gl.public.view
    def get_program_count(self) -> int:
        return int(self.next_program_id) - 1

    @gl.public.view
    def get_payout_amount(self, program_id: str, severity: str) -> int:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")

        p = self.programs[program_id]
        if severity == "CRITICAL":
            return int(p.payout_critical)
        elif severity == "HIGH":
            return int(p.payout_high)
        elif severity == "MEDIUM":
            return int(p.payout_medium)
        elif severity == "LOW":
            return int(p.payout_low)
        else:
            raise gl.vm.UserError("Invalid severity tier")
