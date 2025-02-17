import asyncio
from enum import Enum
from typing import Dict, Tuple

from tqdm import tqdm

from agent_contracts.core.datatypes.dataset.contract import (
    Contract,
    QualifiedRequirement,
    Qualifier,
    Section,
)
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.requirement_checker import RequirementChecker


class ContractStatus(Enum):
    INVALID = None
    SATISFIED = True
    UNSATISFIED = False


class ContractChecker:
    def __init__(self):
        self._req_checker = RequirementChecker()

    async def _check_requirement(
        self, pbar: tqdm, trace: ExecutionPath, qualified_req: QualifiedRequirement
    ) -> Tuple[bool, bool]:
        result = await self._req_checker.check(trace, qualified_req)
        pbar.update(1)
        return qualified_req.requirement.uuid, result

    async def check(
        self, trace: ExecutionPath, contract: Contract
    ) -> Tuple[ContractStatus, Dict[str, bool]]:
        pbar = tqdm(total=len(contract), desc="Contract")
        group = [
            self._check_requirement(pbar, trace, qualified_req)
            for qualified_req in contract
        ]
        check_results = await asyncio.gather(*group)
        req_results = {uuid: res for uuid, res in check_results}
        pbar.close()

        # Is it satisfied?
        satisfied = True
        for req_uuid, result in req_results.items():
            req = contract[req_uuid]
            if req.qualifier == Qualifier.SHOULD:
                continue
            if  req.section == Section.PRECONDITION and not result.satisfied:
                return ContractStatus.INVALID, req_results
            satisfied = satisfied and result.satisfied
        return ContractStatus(satisfied), req_results
