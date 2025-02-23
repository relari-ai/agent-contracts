from typing import Any, List

from pydantic import BaseModel

from agent_contracts.core.datatypes.specifications.requirement import (
    Requirement,
    RequirementRegistry,
)
from agent_contracts.core.utils.nanoid import nanoid


def _serialize_requirements(reqs: List[Requirement], **kwargs) -> List[dict]:
    return [req.to_dict(**kwargs) for req in reqs]


def _deserialize_requirements(data: List[dict]) -> List[Requirement]:
    result = []
    for item in data:
        req_type = item.get("__class__")
        cx = RequirementRegistry.get(req_type)
        result.append(cx.model_validate(item))
    return result


class Contract(BaseModel):
    uuid: str
    name: str
    requirements: List[Requirement]

    def model_post_init(self, __context: Any):
        if not self.uuid:
            self.uuid = f"con-{nanoid(8)}"

    def __len__(self):
        return len(self.requirements)

    def __iter__(self):
        for req in self.requirements:
            if req.type == "precondition":
                yield req
        for req in self.requirements:
            if req.type == "pathcondition":
                yield req
        for req in self.requirements:
            if req.type == "postcondition":
                yield req

    def __getitem__(self, uuid: str):
        for req in self.requirements:
            if req.uuid == uuid:
                return req
        raise ValueError(f"Requirement with uuid {uuid} not found")

    def __contains__(self, uuid: str):
        return any(req.uuid == uuid for req in self.requirements)

    def __str__(self):
        return f"Contract(uuid={self.uuid}, name={self.name}, requirements={self.requirements})"

    def model_dump(self, **kwargs) -> dict:
        dump = super().model_dump(**kwargs)
        dump["requirements"] = _serialize_requirements(self.requirements, **kwargs)
        return dump

    @classmethod
    def model_validate(cls, data: dict) -> "Contract":
        requirements = _deserialize_requirements(data["requirements"])
        return cls(uuid=data["uuid"], name=data["name"], requirements=requirements)


# class Requirements(BaseModel):
#     must: List[RequirementType] = Field(default_factory=list)
#     should: List[RequirementType] = Field(default_factory=list)

#     class Config:
#         arbitrary_types_allowed = True

#     def __len__(self):
#         return len(self.must) + len(self.should)

#     def __iter__(self) -> Generator[RequirementType, None, None]:
#         for req in self.must:
#             yield QualifiedRequirement(req, Qualifier.MUST)
#         for req in self.should:
#             yield QualifiedRequirement(req, Qualifier.SHOULD)

#     @field_validator("*", mode="before")
#     def convert_none_to_list(cls, value):
#         if value is None:
#             return []
#         return value

#     @field_validator("must", "should", mode="before")
#     def parse_requirements(cls, values):
#         new_list = []
#         for value in values:
#             if isinstance(value, dict):
#                 req_type = value.pop("type")
#                 if req_type == "nl":
#                     new_list.append(NLRequirement(**value))
#                 elif req_type == "deterministic":
#                     new_list.append(DeterministicRequirement(**value))
#                 else:
#                     raise ValueError(f"Unknown type: {req_type}")
#             else:
#                 new_list.append(value)
#         return new_list

#     @field_serializer("must", "should")
#     def serialize_requirements(self, requirements: List[RequirementType], field: str):
#         return [req.model_dump() for req in requirements]


# class Contract(BaseModel):
#     uuid: Optional[str] = None
#     name: str
#     guard: Optional[RegexPattern] = None
#     preconditions: Requirements = Requirements()
#     postconditions: Requirements = Requirements()
#     pathconditions: Requirements = Requirements()

#     def model_post_init(self, __context: Any):
#         if not self.uuid:
#             self.uuid = f"con-{nanoid(8)}"

#     class Config:
#         arbitrary_types_allowed = True

#     def __len__(self):
#         return (
#             len(self.preconditions)
#             + len(self.postconditions)
#             + len(self.pathconditions)
#         )

#     def __iter__(self) -> Generator[RequirementType, None, None]:
#         # Preconditions
#         for req in self.preconditions.must:
#             yield QualifiedRequirement(req, Qualifier.MUST, Section.PRECONDITION)
#         for req in self.preconditions.should:
#             yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PRECONDITION)
#         # Postconditions
#         for req in self.postconditions.must:
#             yield QualifiedRequirement(req, Qualifier.MUST, Section.POSTCONDITION)
#         for req in self.postconditions.should:
#             yield QualifiedRequirement(req, Qualifier.SHOULD, Section.POSTCONDITION)
#         # Pathconditions
#         for req in self.pathconditions.must:
#             yield QualifiedRequirement(req, Qualifier.MUST, Section.PATHCONDITION)
#         for req in self.pathconditions.should:
#             yield QualifiedRequirement(req, Qualifier.SHOULD, Section.PATHCONDITION)

#     @property
#     def is_empty(self):
#         return (
#             self.preconditions.is_empty
#             and self.postconditions.is_empty
#             and self.pathconditions.is_empty
#         )

#     def __getitem__(self, uuid: str) -> QualifiedRequirement:
#         for req in self:
#             if req.requirement.uuid == uuid:
#                 return req
#         raise ValueError(f"Requirement with uuid {uuid} not found")
