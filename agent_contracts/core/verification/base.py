from typing import Optional

from pydantic import BaseModel, field_serializer


class VerificationResults(BaseModel):
    satisfied: bool
    explanation: Optional[str] = None
    info: Optional[BaseModel] = None

    @field_serializer("info")
    def serialize_info(self, value: BaseModel) -> dict:
        # make sure the info is serialized properly
        return value.model_dump() if value else None