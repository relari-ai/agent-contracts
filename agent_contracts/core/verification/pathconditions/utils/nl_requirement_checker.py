import logging
from typing import Dict, List, Optional

import json_repair as json
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_random_exponential

from agent_contracts.core.config import VerificationConfig
from agent_contracts.core.datatypes.verification.exec_path import (
    Action,
    ExecutionPath,
    State,
)
from agent_contracts.core.prompts.provider import PromptProvider
from agent_contracts.core.verification.base import (
    VerificationInstructions,
    VerificationResults,
)

from .exec_path_utils import exec_path_to_str_compact, redact_info

logger = logging.getLogger(__name__)


class StepResult(BaseModel):
    span_id: str
    result: Dict
    reasoning: str
    early_termination: bool


class _Schema(BaseModel):
    reasoning: str
    state_schema: str
    instructions: str
    success_condition: str
    early_termination: str


class Step(BaseModel):
    reasoning: str
    result: str
    early_termination: bool


class _VerifyResult(BaseModel):
    explanation: str
    satisfied: bool


class NLVerificationInfo(BaseModel):
    instructions: Optional[VerificationInstructions] = None
    updates: List[StepResult]
    step_success_condition: str
    step_update_instruction: str


class NLRequirementChecker:
    def __init__(
        self,
        requirement: str,
    ):
        self.client = AsyncOpenAI()
        self.config = VerificationConfig.pathconditions.multi_stage
        self.requirement = requirement
        self.prompt_templates = {
            "init": PromptProvider.get_prompt(self.config.prompts.init),
            "step": PromptProvider.get_prompt(self.config.prompts.step),
            "verify": PromptProvider.get_prompt(self.config.prompts.verify),
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

    async def init(self, exec_path: ExecutionPath) -> None:
        msgs = self.prompt_templates["init"].render(
            exec_path=exec_path_to_str_compact(exec_path),
            requirement=self.requirement,
            early_termination=self.config.early_termination,
        )
        valid = False
        while not valid:
            _schema = await self._completion(
                model=self.config.models.init,
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
        self.early_termination = (
            _schema.early_termination.strip() or "Never terminate early"
        )

    async def step(self, state: State, action: Action) -> StepResult:
        if not self.schema or not self.instructions:
            raise RuntimeError("You have to call init first")
        ctx = self.updates[-1].result if self.updates else self.schema
        action_dump = action.model_dump()
        action_dump["info"] = redact_info(action_dump["info"])
        msgs = self.prompt_templates["step"].render(
            state=state,
            action=action_dump,
            schema=ctx,
            prev_reasoning=self.updates[-1].reasoning if self.updates else None,
            update_instructions=self.instructions,
            early_termination=self.early_termination,
        )
        valid = False
        while not valid:
            result = await self._completion(
                model=self.config.models.step,
                messages=msgs,
                response_format=Step,
                temperature=0.0,
            )
            try:
                parsed_result = json.loads(result.result)
            except json.JSONDecodeError:
                parsed_result = {}
            if all(key in parsed_result for key in self.schema.keys()):
                valid = True
            else:
                logger.debug("Invalid step result, retrying...")
        update = StepResult(
            span_id=action.span_id,
            result=parsed_result,
            reasoning=result.reasoning,
            early_termination=(
                self.config.early_termination and result.early_termination
            ),
        )
        self.updates.append(update)
        return update

    async def verify(self) -> VerificationResults:
        msgs = self.prompt_templates["verify"].render(
            requirement=self.requirement,
            instructions=self.instructions,
            updates=self.updates,
            success_condition=self.success_condition,
        )
        self.verify_result = await self._completion(
            model=self.config.models.verify,
            messages=msgs,
            response_format=_VerifyResult,
        )
        return VerificationResults(
            satisfied=self.verify_result.satisfied,
            explanation=self.verify_result.explanation,
            info=NLVerificationInfo(
                instructions=VerificationInstructions(
                    update=str(self.instructions),
                    early_termination=str(self.early_termination),
                ),
                step_success_condition=str(self.success_condition),
                step_update_instruction=str(self.instructions),
                updates=self.updates,
            ),
        )
