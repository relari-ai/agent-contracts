from dataclasses import dataclass
from enum import Enum
from re import Pattern as RegexPattern
from typing import Any, Generator, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

from agent_contracts.core.datatypes.dataset.requirement import (
    DeterministicRequirement,
    NLRequirement,
)

RequirementType = Union[NLRequirement, DeterministicRequirement]


class Section(Enum):
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    PATHCONDITION = "pathcondition"


class Qualifier(Enum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    SHOULD_NOT = "should_not"

    def apply(self, bool_value: bool) -> bool:
        if self in [Qualifier.MUST, Qualifier.SHOULD]:
            return bool_value
        elif self in [Qualifier.MUST_NOT, Qualifier.SHOULD_NOT]:
            return not bool_value
        else:
            raise ValueError(f"Invalid qualifier: {self}")


@dataclass
class QualifiedRequirement:
    requirement: RequirementType
    qualifier: Qualifier
    section: Optional[Section] = None


# https://www.ietf.org/rfc/rfc2119.txt
class Requirements(BaseModel):
    must: List[RequirementType] = Field(default_factory=list)
    must_not: List[RequirementType] = Field(default_factory=list)
    should: List[RequirementType] = Field(default_factory=list)
    should_not: List[RequirementType] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def __len__(self):
        return (
            len(self.must)
            + len(self.must_not)
            + len(self.should)
            + len(self.should_not)
        )

    def __iter__(self) -> Generator[RequirementType, None, None]:
        for req in self.must:
            yield QualifiedRequirement(req, Qualifier.MUST)
        for req in self.must_not:
            yield QualifiedRequirement(req, Qualifier.MUST_NOT)
        for req in self.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD)
        for req in self.should_not:
            yield QualifiedRequirement(req, Qualifier.SHOULD_NOT)

    @field_validator("*", mode="before")
    def convert_none_to_list(cls, value):
        if value is None:
            return []
        return value

    @field_validator("must", "must_not", "should", "should_not", mode="before")
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

    @field_serializer("must", "must_not", "should", "should_not")
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
            self.uuid = str(uuid4())

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
        for req in self.preconditions.must_not:
            yield QualifiedRequirement(req, Qualifier.MUST_NOT, Section.PRECONDITION)
        for req in self.preconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PRECONDITION)
        for req in self.preconditions.should_not:
            yield QualifiedRequirement(req, Qualifier.SHOULD_NOT, Section.PRECONDITION)
        # Postconditions
        for req in self.postconditions.must:
            yield QualifiedRequirement(req, Qualifier.MUST, Section.POSTCONDITION)
        for req in self.postconditions.must_not:
            yield QualifiedRequirement(req, Qualifier.MUST_NOT, Section.POSTCONDITION)
        for req in self.postconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.POSTCONDITION)
        for req in self.postconditions.should_not:
            yield QualifiedRequirement(req, Qualifier.SHOULD_NOT, Section.POSTCONDITION)
        # Pathconditions
        for req in self.pathconditions.must:
            yield QualifiedRequirement(req, Qualifier.MUST, Section.PATHCONDITION)
        for req in self.pathconditions.must_not:
            yield QualifiedRequirement(req, Qualifier.MUST_NOT, Section.PATHCONDITION)
        for req in self.pathconditions.should:
            yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PATHCONDITION)
        for req in self.pathconditions.should_not:
            yield QualifiedRequirement(req, Qualifier.SHOULD_NOT, Section.PATHCONDITION)

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
