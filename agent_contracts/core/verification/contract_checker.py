from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from tqdm.asyncio import tqdm

from agent_contracts.core.datatypes.specifications.contract import Contract
from agent_contracts.core.datatypes.specifications.requirement import Requirement, Level
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.base import VerificationResults
from enum import Flag, auto


class ContractStatus(Enum):
    INVALID = None
    SATISFIED = True
    UNSATISFIED = False


class Condition(Flag):
    PRECONDITIONS = auto()
    POSTCONDITIONS = auto()
    PATHCONDITIONS = auto()

    ALL = PRECONDITIONS | POSTCONDITIONS | PATHCONDITIONS

    @classmethod
    def from_string(cls, s: str) -> "Condition":
        if s == "precondition":
            return cls.PRECONDITIONS
        elif s == "postcondition":
            return cls.POSTCONDITIONS
        elif s == "pathcondition":
            return cls.PATHCONDITIONS

    def matches(self, req: Requirement) -> bool:
        return self.from_string(req.type) in self


@dataclass
class ContractVerificationResults:
    satisfied: bool
    info: Dict[str, bool]


class ContractChecker:
    @staticmethod
    def prepare_requirement_input(req: Requirement, exec_path: ExecutionPath) -> dict:
        if req.type == "precondition":
            return exec_path.input
        elif req.type == "pathcondition":
            return exec_path
        elif req.type == "postcondition":
            if req.on == "output":
                return exec_path.output
            elif req.on == "conversation":
                return exec_path.conversation
            else:
                raise ValueError(f"Invalid requirement type: {req.type}")
        else:
            raise ValueError(f"Invalid requirement type: {req.type}")

    def _compute_contract_status(
        self, contract: Contract, check_results: List[VerificationResults]
    ) -> ContractStatus:
        preconditions, musts = True, True
        for req, result in zip(contract, check_results):
            if req.level == Level.SHOULD:
                # Should do not affect the contract satisfiability
                continue
            if req.type == "precondition":
                preconditions = preconditions and result.satisfied
            else:
                musts = musts and result.satisfied
            if not preconditions:
                return ContractStatus.INVALID
            if not musts:
                return ContractStatus.UNSATISFIED
        return ContractStatus.SATISFIED

    async def check(
        self,
        trace: ExecutionPath,
        contract: Contract,
        progress: bool = True,
        filter: Condition = Condition.ALL,
    ) -> ContractVerificationResults:
        group = [
            req.check(self.prepare_requirement_input(req, trace))
            for req in contract
            if filter.matches(req)
        ]
        check_results = await tqdm.gather(
            *group, desc=f"Contract {contract.name}", disable=not progress
        )
        return ContractVerificationResults(
            satisfied=self._compute_contract_status(contract, check_results),
            info={req.uuid: result for req, result in zip(contract, check_results)},
        )
