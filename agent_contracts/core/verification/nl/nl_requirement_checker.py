from dataclasses import dataclass
from json import dumps as json_dump
from typing import Any
import json_repair as json
from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_contracts.core.datatypes.verification.exec_path import (
    Action,
    ExecutionPath,
    State,
)
from agent_contracts.core.datatypes.dataset.requirement import NLRequirement
from agent_contracts.core.prompts.provider import PromptProvider

from .exec_path_utils import exec_path_to_str_compact
import logging

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
            exec_path=exec_path_to_str_compact(exec_path),
            requirement=requirement.requirement,
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
        self.instructions = _schema.instructions.strip()
        self.success_condition = _schema.success_condition.strip()

    async def step(self, state: State, action: Action) -> None:
        if not self.schema or not self.instructions:
            raise RuntimeError("You have to call init first")
        ctx = self.updates[-1].result if self.updates else self.schema
        prompt = PromptProvider.get_prompt("verification/nl/step")
        action_dump = action.model_dump()
        x = json_dump(action_dump["info"])
        action_dump["info"] = redact_info(action_dump["info"])
        y = json_dump(action_dump["info"])
        delta = len(x) - len(y)
        print(delta)
        msgs = prompt.render(
            state=state,
            requirement=self.requirement.requirement,
            instructions=self.instructions,
            schema=ctx,
            action=action_dump,
        )
        tokens = int(sum(len(msg["content"]) for msg in msgs) / 4.2)
        if tokens > 120000:
            raise RuntimeError("Too many tokens")
        # with open("usr_msg.txt", "w") as f:
        #     f.write(msgs[-1]["content"])
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
            requirement=self.requirement.requirement,
            instructions=self.instructions,
            updates=self.updates,
            success_condition=self.success_condition,
        )
        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=msgs,
            response_format=_VerifyResult,
        )
        self.verify_result = response.choices[0].message.parsed
        return self.verify_result.satisfied
