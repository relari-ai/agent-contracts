from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel


class DeterministicRequirement(BaseModel):
    uuid: Optional[str] = None
    variant: str
    args: Dict[str, Any]
    
    @property
    def name(self):
        return self.variant

    def model_post_init(self, __context: Any):
        if not self.uuid:
            self.uuid = str(uuid4())
    
    def model_dump(self):
        return {"type": "deterministic", **super().model_dump()}


class NLRequirement(BaseModel):
    uuid: Optional[str] = None
    requirement: str  # No leading underscore; directly named `requirement`

    def __init__(self, requirement: str, uuid: Optional[str] = None):
        super().__init__(uuid=uuid, requirement=requirement)

    def model_post_init(self, __context: Any):
        if not self.uuid:
            self.uuid = str(uuid4())

    @property
    def name(self):
        return self.requirement

    def model_dump(self):
        return {"type": "nl", **super().model_dump()}
