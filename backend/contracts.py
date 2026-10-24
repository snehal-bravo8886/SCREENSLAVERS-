"""HTTP request contracts, intentionally independent of internal Python engine objects."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_cycles: bool = True

class StressTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    excluded_transaction_id: str | None = Field(default=None, min_length=1, max_length=128)
    excluded_transaction_ids: list[str] | None = Field(default=None, min_length=1)

class ReviewStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["to_do", "in_progress", "done"]
