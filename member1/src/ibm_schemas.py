"""Versioned native-simulation-step models for IBM's archived graph transactions.

Crucial: these are not ISO-datetime observations and must not be converted into
minutes without archive-specific verification. Member B uses simulation_step
and the alert start_step/end_step fields for all temporal calculations.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class IBMStepTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: str = Field(min_length=1)
    source_account: str = Field(min_length=1)
    destination_account: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    currency: Literal["XXX"]
    timestamp: None
    simulation_step: int = Field(ge=0)
    time_unit: Literal["simulation_step"]
    id_is_derived: Literal[True]


class IBMStepAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: str = Field(pattern=r"^DET-[A-Z]+-\d+$")
    detector: Literal["fan_in", "fan_out", "rapid_pass_through", "temporal_cycle"]
    account_ids: List[str] = Field(min_length=1)
    transaction_ids: List[str] = Field(min_length=1)
    start_time: None
    end_time: None
    start_step: int = Field(ge=0)
    end_step: int = Field(ge=0)
    time_unit: Literal["simulation_step"]
    features: Dict[str, Any]
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def step_bounds(self):
        if self.end_step < self.start_step:
            raise ValueError("end_step cannot precede start_step")
        return self
