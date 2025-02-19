from agent_contracts.core.datatypes.dataset.contract import QualifiedRequirement
from agent_contracts.core.datatypes.dataset.requirement import (
    DeterministicRequirement,
    NLRequirement,
)
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath

from .base import VerificationResults
from .nl.nl_requirement_checker import NLRequirementChecker


class RequirementChecker:
    @staticmethod
    async def check(
        exec_path: ExecutionPath, requirement: QualifiedRequirement
    ) -> VerificationResults:
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
    ) -> VerificationResults:
        checker = NLRequirementChecker(requirement)
        early_termination = False
        await checker.init(exec_path)
        for state in exec_path.states:
            if early_termination:
                break
            for action in state.actions:
                update = await checker.step(state, action)
                early_termination = update.early_termination
                if early_termination:
                    break
        return await checker.verify()

    @staticmethod
    async def _check_deterministic_requirement(
        exec_path: ExecutionPath, requirement: DeterministicRequirement
    ) -> VerificationResults:
        return VerificationResults(satisfied=True)
