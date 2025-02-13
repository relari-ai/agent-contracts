from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.datatypes.dataset.contract import QualifiedRequirement
from agent_contracts.core.datatypes.verification.requirement import (
    DeterministicRequirement,
    NLRequirement,
)
from .nl.nl_requirement_checker import NLRequirementChecker
from typing import Tuple


class RequirementChecker:
    @staticmethod
    async def check(
        exec_path: ExecutionPath, requirement: QualifiedRequirement
    ) -> Tuple[str, bool]:
        if isinstance(requirement.requirement, NLRequirement):
            return await RequirementChecker._check_nl_requirement(
                exec_path, requirement
            )
        elif isinstance(requirement.requirement, DeterministicRequirement):
            return await RequirementChecker._check_deterministic_requirement(
                exec_path, requirement
            )
        else:
            raise ValueError(f"Unsupported requirement type: {type(requirement)}")

    @staticmethod
    async def _check_nl_requirement(
        exec_path: ExecutionPath, requirement: NLRequirement
    ) -> bool:
        checker = NLRequirementChecker(requirement)
        await checker.init(exec_path, requirement)
        for state in exec_path.states:
            for action in state.actions:
                await checker.step(state, action)
        return await checker.verify()

    @staticmethod
    async def _check_deterministic_requirement(
        exec_path: ExecutionPath, requirement: DeterministicRequirement
    ) -> bool:
        return True
