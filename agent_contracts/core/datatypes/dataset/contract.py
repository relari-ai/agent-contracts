from dataclasses import dataclass
from enum import Enum
from re import Pattern as RegexPattern
from typing import Any, Generator, List, Optional, Union

from pydantic import BaseModel, Field, field_serializer, field_validator

from agent_contracts.core.datatypes.dataset.requirement import (
    DeterministicRequirement,
    NLRequirement,
)
from agent_contracts.core.utils.nanoid import nanoid

RequirementType = Union[NLRequirement, DeterministicRequirement]


class Section(Enum):
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    PATHCONDITION = "pathcondition"


class Qualifier(Enum):
    MUST = "must"
    SHOULD = "should"


@dataclass
class QualifiedRequirement:
    requirement: RequirementType
    qualifier: Qualifier
    section: Optional[Section] = None


# https://www.ietf.org/rfc/rfc2119.txt
class Requirements(BaseModel):
    must: List[RequirementType] = Field(default_factory=list)
    should: List[RequirementType] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def __len__(self):
        return len(self.must) + len(self.should)

    def __iter__(self) -> Generator[RequirementType, None, None]:
        for req in self.must:
            yield QualifiedRequirement(req, Qualifier.MUST)
        for req in self.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD)

    @field_validator("*", mode="before")
    def convert_none_to_list(cls, value):
        if value is None:
            return []
        return value

    @field_validator("must", "should", mode="before")
    def parse_requirements(cls, values):
        new_list = []
        for value in values:
            if isinstance(value, dict):
                req_type = value.pop("type")
                if req_type == "nl":
                    new_list.append(NLRequirement(**value))
                elif req_type == "deterministic":
                    new_list.append(DeterministicRequirement(**value))
                else:
                    raise ValueError(f"Unknown type: {req_type}")
            else:
                new_list.append(value)
        return new_list

    @field_serializer("must", "should")
    def serialize_requirements(self, requirements: List[RequirementType], field: str):
        return [req.model_dump() for req in requirements]


class Contract(BaseModel):
    uuid: Optional[str] = None
    name: str
    condition: Optional[RegexPattern] = None
    preconditions: Requirements = Requirements()
    postconditions: Requirements = Requirements()
    pathconditions: Requirements = Requirements()

    def model_post_init(self, __context: Any):
        if not self.uuid:
            self.uuid = f"con-{nanoid(8)}"

    class Config:
        arbitrary_types_allowed = True

    def __len__(self):
        return (
            len(self.preconditions)
            + len(self.postconditions)
            + len(self.pathconditions)
        )

    def __iter__(self) -> Generator[RequirementType, None, None]:
        # Preconditions
        for req in self.preconditions.must:
            yield QualifiedRequirement(req, Qualifier.MUST, Section.PRECONDITION)
        for req in self.preconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PRECONDITION)
        # Postconditions
        for req in self.postconditions.must:
            yield QualifiedRequirement(req, Qualifier.MUST, Section.POSTCONDITION)
        for req in self.postconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.POSTCONDITION)
        # Pathconditions
        for req in self.pathconditions.must:
            yield QualifiedRequirement(req, Qualifier.MUST, Section.PATHCONDITION)
        for req in self.pathconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PATHCONDITION)

    @property
    def is_empty(self):
        return (
            self.preconditions.is_empty
            and self.postconditions.is_empty
            and self.pathconditions.is_empty
        )

    def __getitem__(self, uuid: str) -> QualifiedRequirement:
        for req in self:
            if req.requirement.uuid == uuid:
                return req
        raise ValueError(f"Requirement with uuid {uuid} not found")
