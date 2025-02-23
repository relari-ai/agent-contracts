from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_random_exponential

from agent_contracts.core.datatypes.specifications.requirement import (
    BasePostcondition,
)
from agent_contracts.core.prompts.provider import PromptProvider
from agent_contracts.core.verification.base import VerificationResults


class _VerifyResult(BaseModel):
    explanation: str
    satisfied: bool


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
async def _completion(client: AsyncOpenAI, **kwargs) -> BaseModel:
    response = await client.beta.chat.completions.parse(**kwargs)
    return response.choices[0].message.parsed


class Postcondition(BasePostcondition):
    requirement: str = Field(...)

    def __init__(self, requirement: str, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = requirement
        super().__init__(requirement=requirement, **kwargs)

    @property
    def name(self) -> str:
        return self.requirement

    async def check(self, output: dict) -> VerificationResults:
        client = AsyncOpenAI()
        prompt = PromptProvider.get_prompt(f"verification/postcondition/{self.on}")
        msgs = prompt.render(requirement=self.requirement, system_output=output)
        result = await _completion(
            client=client,
            model="gpt-4o-mini",
            messages=msgs,
            response_format=_VerifyResult,
        )
        return VerificationResults(
            satisfied=result.satisfied, explanation=result.explanation
        )
