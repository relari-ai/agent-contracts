from pydantic import Field

from agent_contracts.core.datatypes.specifications.requirement import (
    BasePathcondition,
)
from agent_contracts.core.datatypes.verification import ExecutionPath
from agent_contracts.core.verification.base import VerificationResults

from .utils.nl_requirement_checker import NLRequirementChecker


class MultiStagePathcondition(BasePathcondition):
    requirement: str = Field(...)

    def __init__(self, requirement: str, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = requirement
        super().__init__(requirement=requirement, **kwargs)

    @property
    def name(self) -> str:
        return self.requirement

    async def check(self, exec_path: ExecutionPath) -> VerificationResults:
        checker = NLRequirementChecker(self.requirement)
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
