"""
Canonical Data Schemas for Team Screenslavers / Screenslavers
Strictly adheres to Section 8.1 & 8.2 of the Team Product Blueprint.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class CanonicalTransaction(BaseModel):
    """
    Section 8.1: Canonical transaction model.
    Guarantees account IDs as strings, positive amounts, and ISO-8601 timestamps.
    """
    transaction_id: str = Field(..., description="Unique transaction ID from source dataset")
    source_account: str = Field(..., description="Source/originator account ID (as string)")
    destination_account: str = Field(..., description="Destination/beneficiary account ID (as string)")
    amount: float = Field(..., gt=0, description="Transaction transfer amount (must be > 0)")
    currency: str = Field(default="XXX", description="ISO 4217 currency; XXX means not provided by source")
    timestamp: str = Field(..., description="ISO-8601 formatted timestamp string")

    @field_validator("source_account", "destination_account", mode="before")
    @classmethod
    def ensure_string_account(cls, v: Any) -> str:
        if v is None:
            raise ValueError("Account ID cannot be None")
        return str(v).strip()

    @field_validator("transaction_id", mode="before")
    @classmethod
    def ensure_string_tx_id(cls, v: Any) -> str:
        if v is None:
            raise ValueError("Transaction ID cannot be None")
        return str(v).strip()


class DetectionAlert(BaseModel):
    """
    Section 8.2: Detection alert model emitted by rule detectors.
    Uses 'DET-*' namespace to avoid collision with source dataset alert IDs.
    """
    alert_id: str = Field(..., description="Unique alert ID e.g. DET-0001")
    detector: str = Field(..., description="Detector rule name e.g. rapid_pass_through, fan_in, fan_out, cycle")
    account_ids: List[str] = Field(..., description="List of involved account IDs")
    transaction_ids: List[str] = Field(..., description="List of exact supporting transaction IDs")
    start_time: str = Field(..., description="ISO-8601 start timestamp of pattern window")
    end_time: str = Field(..., description="ISO-8601 end timestamp of pattern window")
    features: Dict[str, Any] = Field(default_factory=dict, description="Transparent feature measurements")
    reason: str = Field(..., description="Human-readable explanation of why this was flagged")


class EvaluationLabel(BaseModel):
    """
    Private evaluation label storage.
    CRITICAL: Never exposed to detection algorithms, scoring, or user interface.
    Used exclusively in post-hoc benchmark evaluation (Recall@K).
    """
    transaction_id: str
    is_sar: Optional[int] = None
    source_alert_id: Optional[str] = None
    source_alert_type: Optional[str] = None
