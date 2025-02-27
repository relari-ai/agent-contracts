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

    @property
    def preconditions(self):
        return [req for req in self.requirements if req.type == "precondition"]

    @property
    def pathconditions(self):
        return [req for req in self.requirements if req.type == "pathcondition"]

    @property
    def postconditions(self):
        return [req for req in self.requirements if req.type == "postcondition"]

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
