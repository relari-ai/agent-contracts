from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent_contracts.core.datatypes.trace import Trace
from .frameworks import parse_trace


class Action(BaseModel):
    span_id: str = Field(
        ..., alias="spanId", description="A unique identifier for the action"
    )
    name: Optional[str] = Field(..., description="The name of the action")
    info: Dict[str, Any] = Field(
        default={}, description="Additional information about the action"
    )

    class Config:
        populate_by_name = True


class State(BaseModel):
    span_id: str = Field(
        ..., alias="spanId", description="A unique identifier for the state"
    )
    name: str = Field(..., description="The name of the state")
    info: Dict[str, Any] = Field(
        default={}, description="Additional information about the state"
    )
    actions: List[Action] = Field(
        default=[], description="The actions leading to the next state"
    )

    class Config:
        populate_by_name = True


class ExecutionPath(BaseModel):
    trace_id: str = Field(..., description="The trace ID")
    states: List[State]

    def model_post_init(self, __context):
        # Verify no duplicate span IDs
        span_ids = [state.span_id for state in self.states] + [
            action.span_id for state in self.states for action in state.actions
        ]
        if not len(set(span_ids)) == len(span_ids):
            raise ValueError("Duplicate span IDs in execution fragment")

    def __repr__(self):
        """
        Provide a readable string representation for the execution fragment.
        """
        sequence = []
        for state in self.states:
            repr = state.name
            if not state.actions:
                repr += " ---->"
            else:
                repr += " --(" + "|".join([act.name for act in state.actions]) + ")-->"
            sequence.append(repr)
        sequence.append("__end__")
        return "ExecutionPath[" + " ".join(sequence) + "]"

    def to_mermaid(self):
        """
        Provide a mermaid string representation for the execution fragment.
        """
        mermaid_str = "stateDiagram-v2\n"
        for i in range(len(self.states) - 1):
            current_state = self.states[i]
            next_state = self.states[i + 1]
            actions = current_state.actions
            if actions:
                for action in actions:
                    mermaid_str += f"    {current_state.name} --> {next_state.name}: {action.name}\n"
            else:
                mermaid_str += f"    {current_state.name} --> {next_state.name}\n"

        return mermaid_str

    def pprint(self):
        for state in self.states:
            print(state.name)
            for action in state.actions:
                print(f"    {action.name}")

    def fill(self, trace: Trace):
        for state in self.states:
            state_span = trace.get_span_by_id(state.span_id)
            state.info = state_span.attributes
            for action in state.actions:
                action_span = trace.get_span_by_id(action.span_id)
                action.info = action_span.attributes

    def iterate(self):
        for state in self.states:
            yield state
            for action in state.actions:
                yield action

    def to_json(self, indent: int | None = None):
        return self.model_dump_json(indent=indent, by_alias=True)

    @staticmethod
    def from_json(json_str: str):
        return ExecutionPath.model_validate_json(json_str)

    def save(self, path: Path):
        json_str = self.to_json()
        with open(path, "w") as f:
            f.write(json_str)

    @staticmethod
    def load(path: Path):
        with open(path, "r") as f:
            return ExecutionPath.model_validate_json(f.read())

    @classmethod
    def from_trace(cls, trace: Trace) -> "ExecutionPath":
        states = [State.model_validate(state) for state in parse_trace(trace)]
        exec_path = cls(trace_id=trace.trace_id, states=states)
        exec_path.fill(trace)
        return exec_path
