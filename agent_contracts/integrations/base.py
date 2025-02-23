from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TraceInfo(BaseModel):
    trace_id: str
    project_name: Optional[str] = None
    run_id: Optional[str] = None
    specifications_id: Optional[str] = None
    scenario_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    class Config:
        frozen = True


class RunIdInfo(BaseModel):
    run_id: str
    project_name: Optional[str] = None
    specifications_id: Optional[str] = None
    start_time: datetime
    end_time: datetime

    class Config:
        frozen = True
