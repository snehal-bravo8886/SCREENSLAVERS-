"""HTTP request contracts, intentionally independent of internal Python engine objects."""
from pydantic import BaseModel, ConfigDict, Field

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_cycles: bool = True

class StressTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    excluded_transaction_id: str = Field(min_length=1, max_length=128)
