import logging
from typing import Any, Dict, List

import json_repair as json
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

from agent_contracts.core.datatypes.dataset.requirement import NLRequirement
from agent_contracts.core.datatypes.verification.exec_path import (
    Action,
    ExecutionPath,
    State,
)
from agent_contracts.core.prompts.provider import PromptProvider

from .exec_path_utils import exec_path_to_str_compact
from agent_contracts.core.verification.base import VerificationResults

logger = logging.getLogger(__name__)


def redact_info(info: Any):
    if isinstance(info, dict):
        # Remove sensitive keys
        for key in ["otel", "span", "token_usage"]:
            info.pop(key, None)

        # If the dict has exactly the keys {"lc", "type", "id", "kwargs"},
        # then unwrap it by redacting and returning its "kwargs" value.
        if set(info.keys()) == {"lc", "type", "id", "kwargs"}:
            return redact_info(info["kwargs"])

        # Recursively update each value in the dictionary.
        for k, v in info.items():
            info[k] = redact_info(v)
        return info

    elif isinstance(info, list):
        return [redact_info(item) for item in info]

    elif isinstance(info, str):
        if info.startswith("data:image"):
            return "__REDACTED__"
    return info


class StepResult(BaseModel):
    span_id: str
    result: Dict
    reasoning: str


class _Schema(BaseModel):
    reasoning: str
    state_schema: str
    instructions: str
    success_condition: str


class Step(BaseModel):
    result: str
    reasoning: str


class _VerifyResult(BaseModel):
    explanation: str
    satisfied: bool


class NLVerificationInfo(BaseModel):
    updates: List[StepResult]
    step_success_condition: str
    step_update_instruction: str


class NLRequirementChecker:
    def __init__(self, requirement: NLRequirement, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model
        self.requirement = requirement
        self.prompt_templates = {
            "init": PromptProvider.get_prompt("verification/nl/init"),
            "step": PromptProvider.get_prompt("verification/nl/step"),
            "verify": PromptProvider.get_prompt("verification/nl/verify"),
        }
        self.schema = None
        self.instructions = None
        self.success_condition = None
        self.updates = []
        self.verify_result = None

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def _completion(self, **kwargs) -> BaseModel:
        response = await self.client.beta.chat.completions.parse(**kwargs)
        return response.choices[0].message.parsed

    async def init(self, exec_path: ExecutionPath, requirement: NLRequirement) -> None:
        msgs = self.prompt_templates["init"].render(
            exec_path=exec_path_to_str_compact(exec_path),
            requirement=requirement.requirement,
        )
        valid = False
        while not valid:
            _schema = await self._completion(
                model=self.model,
                messages=msgs,
                response_format=_Schema,
            )
            try:
                parsed_schema = json.loads(_schema.state_schema)
            except json.JSONDecodeError:
                parsed_schema = {}
            if parsed_schema:
                valid = True
            else:
                logger.debug("Invalid schema, retrying...")
        self.schema = parsed_schema
        self.instructions = _schema.instructions.strip()
        self.success_condition = _schema.success_condition.strip()

    async def step(self, state: State, action: Action) -> None:
        if not self.schema or not self.instructions:
            raise RuntimeError("You have to call init first")
        ctx = self.updates[-1].result if self.updates else self.schema
        action_dump = action.model_dump()
        action_dump["info"] = redact_info(action_dump["info"])
        msgs = self.prompt_templates["step"].render(
            state=state,
            requirement=self.requirement.requirement,
            instructions=self.instructions,
            schema=ctx,
            action=action_dump,
        )
        valid = False
        while not valid:
            result = await self._completion(
                model=self.model,
                messages=msgs,
                response_format=Step,
            )
            try:
                parsed_result = json.loads(result.result)
            except json.JSONDecodeError:
                parsed_result = {}
            if all(key in parsed_result for key in self.schema.keys()):
                valid = True
            else:
                logger.debug("Invalid step result, retrying...")
        self.updates.append(
            StepResult(
                span_id=action.span_id, result=parsed_result, reasoning=result.reasoning
            )
        )

    async def verify(self) -> VerificationResults:
        msgs = self.prompt_templates["verify"].render(
            requirement=self.requirement.requirement,
            instructions=self.instructions,
            updates=self.updates,
            success_condition=self.success_condition,
        )
        self.verify_result = await self._completion(
            model=self.model,
            messages=msgs,
            response_format=_VerifyResult,
        )
        return VerificationResults(
            satisfied=self.verify_result.satisfied,
            explanation=self.verify_result.explanation,
            info=NLVerificationInfo(
                step_success_condition=str(self.success_condition),
                step_update_instruction=str(self.instructions),
                updates=self.updates,
            ),
        )
