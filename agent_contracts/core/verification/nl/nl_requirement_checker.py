from dataclasses import dataclass
from json import dumps as json_dump

import json_repair as json
from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_contracts.core.datatypes.verification.exec_path import (
    Action,
    ExecutionPath,
    State,
)
from agent_contracts.core.datatypes.verification.requirement import NLRequirement
from agent_contracts.core.prompts.provider import PromptProvider

from .exec_path_utils import exec_path_to_str_compact
import logging

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    span_id: str
    result: str
    reasoning: str


class _Schema(BaseModel):
    reasoning: str
    state_schema: str
    instructions: str
    success_condition: str

    class Config:
        json_encoders = {
            # Prevent the default method from being serialized
            type: lambda v: str(v) if callable(v) else v
        }


class _Step(BaseModel):
    result: str
    reasoning: str


class _VerifyResult(BaseModel):
    explanation: str
    satisfied: bool


class NLRequirementChecker:
    def __init__(self, requirement: NLRequirement, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model
        self.requirement = requirement
        self.schema = None
        self.instructions = None
        self.success_condition = None
        self.updates = []
        self.verify_result = None

    async def init(self, exec_path: ExecutionPath, requirement: NLRequirement) -> None:
        prompt = PromptProvider.get_prompt("verification/nl/init")
        msgs = prompt.render(
            exec_path=exec_path_to_str_compact(exec_path), requirement=requirement
        )
        valid = False
        while not valid:
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=msgs,
                response_format=_Schema,
            )
            _schema = response.choices[0].message.parsed
            try:
                parsed_schema = json.loads(_schema.state_schema)
            except json.JSONDecodeError:
                parsed_schema = {}
            if parsed_schema:
                valid = True
            else:
                logger.debug("Invalid schema, retrying...")
        self.schema = parsed_schema
        self.instructions = _schema.instructions
        self.success_condition = _schema.success_condition

    async def step(self, state: State, action: Action) -> None:
        if not self.schema or not self.instructions:
            raise RuntimeError("You have to call init first")
        ctx = self.updates[-1].result if self.updates else self.schema
        prompt = PromptProvider.get_prompt("verification/nl/step")
        msgs = prompt.render(
            state=state,
            requirement=self.requirement,
            instructions=self.instructions,
            schema=json_dump(ctx, indent=2),
            action=json_dump(action.model_dump(), indent=2),
        )
        valid = False
        while not valid:
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=msgs,
                response_format=_Step,
            )
            result = response.choices[0].message.parsed
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

    async def verify(self) -> bool:
        prompt = PromptProvider.get_prompt("verification/nl/verify")
        msgs = prompt.render(
            requirement=self.requirement,
            instructions=self.instructions,
            results=self.updates[-1].result,
            success_condition=self.success_condition,
        )
        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=msgs,
            response_format=_VerifyResult,
        )
        self.verify_result = response.choices[0].message.parsed
        return self.verify_result.satisfied
