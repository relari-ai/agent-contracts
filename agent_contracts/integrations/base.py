from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TraceInfo(BaseModel):
    trace_id: str
    project_name: Optional[str] = None
    run_id: Optional[str] = None
    dataset_id: Optional[str] = None
    scenario_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
