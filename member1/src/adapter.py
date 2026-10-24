"""Fail-closed IBM AMLSim-compatible CSV adapter.

The older IBM/AMLSim sample contains TXN_ID / ACCOUNT_ID / COUNTER_PARTY_ACCOUNT_NUM /
TXN_AMOUNT_ORIG / start (simulation steps). New AMLSim exports often contain
tran_id / orig_acct / bene_acct / base_amt / tran_timestamp. Neither layout's
integer step is assumed to be a minute: caller must explicitly supply base
and step duration. Original SAR/alert/scenario fields are evaluation-only.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from .schemas import CanonicalTransaction, EvaluationLabel

logger = logging.getLogger(__name__)

FIELD_ALIASES = {
    "transaction_id": ["tran_id", "transaction_id", "txn_id", "tx_id", "id", "trans_id"],
    "source_account": ["orig_acct", "account_id", "source_account", "from_account", "sender", "src", "source", "from", "source_id"],
    "destination_account": ["bene_acct", "counter_party_account_num", "destination_account", "to_account", "receiver", "dst", "target", "destination", "to", "target_id"],
    "amount": ["base_amt", "txn_amount_orig", "amount_paid", "amount", "amt", "weight"],
    "timestamp": ["tran_timestamp", "timestamp", "start", "step", "time", "date_time", "day"],
    "currency": ["currency", "payment_currency", "cur"],
    "count": ["tx_count", "transaction_count"],
    "period_end": ["end", "end_step"],
    "is_sar": ["is_sar", "is_laundering", "islaundering", "label", "target_label"],
    "source_alert_id": ["alert_id", "source_alert_id", "scenario_id"],
    "source_alert_type": ["alert_type", "model_type", "scenario_type"],
}
NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
INVALID_IDENTIFIERS = {"", "none", "null", "nan", "nat", "na", "n/a"}


def _find_column(columns: List[str], names: List[str]) -> Optional[str]:
    known = {str(k).strip().lower().replace(" ", "_"): k for k in columns}
    return next((known[k] for k in names if k in known), None)


def _required_id(value: Any) -> str:
    if pd.isna(value):
        raise ValueError("Missing identifier")
    text = str(value).strip()
    if text.lower() in INVALID_IDENTIFIERS:
        raise ValueError("Blank or invalid identifier")
    return text


def _parse_money(raw: Any) -> float:
    try:
        val = Decimal(str(raw).strip())
        if not val.is_finite() or val <= 0:
            raise ValueError("Amount must be finite and positive")
        rounded = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if rounded <= 0:
            raise ValueError("Amount rounds to zero at two decimals")
        if rounded > Decimal("1e15"):
            raise ValueError("Amount exceeds prototype precision limit")
        return float(rounded)
    except (InvalidOperation, OverflowError) as e:
        raise ValueError("Amount must be a finite number") from e


def parse_timestamp_to_iso(value: Any, base_datetime: Optional[datetime] = None,
                           step_minutes: Optional[float] = None) -> str:
    """Numeric simulation steps are converted ONLY with explicit metadata."""
    if pd.isna(value) or str(value).strip().lower() in INVALID_IDENTIFIERS:
        raise ValueError("Missing or invalid timestamp")
    text = str(value).strip()
    if NUMERIC.fullmatch(text):
        if base_datetime is None or step_minutes is None:
            raise ValueError("Simulation step requires explicit base_datetime and step_minutes")
        num = float(text)
        if not math.isfinite(num) or not math.isfinite(float(step_minutes)) or step_minutes <= 0:
            raise ValueError("Invalid simulation-step duration")
        if base_datetime.tzinfo is None:
            raise ValueError("Simulation base_datetime must include a timezone")
        try:
            return (base_datetime + timedelta(minutes=num * step_minutes)).astimezone(timezone.utc).isoformat()
        except OverflowError as e:
            raise ValueError("Simulation step outside supported timestamp range") from e
    # Avoid pandas' loose interpretation of text like "NaT" and "not-a-time".
    parsed = pd.to_datetime(text, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("Invalid ISO/date timestamp")
    return parsed.isoformat()


def _parse_label(raw: Any) -> Optional[int]:
    val = str(raw).strip().lower()
    if val in {"1", "1.0", "true", "yes"}:
        return 1
    if val in {"0", "0.0", "false", "no"}:
        return 0
    return None  # Not asserted to be a clean normal transaction


class TransactionIngestionEngine:
    def __init__(self, *, base_datetime: Optional[datetime] = None,
                 step_minutes: Optional[float] = None,
                 default_currency: str = "XXX",  # ISO 4217: no currency specified
                 allow_derived_ids: bool = False):
        self.base_datetime = base_datetime
        self.step_minutes = step_minutes
        self.default_currency = default_currency
        self.allow_derived_ids = allow_derived_ids
        self.skipped_records: List[Dict[str, Any]] = []
        self.audit: Dict[str, Any] = {}

    def load_from_dataframe(self, df: pd.DataFrame) -> Tuple[List[CanonicalTransaction], Dict[str, EvaluationLabel]]:
        self.skipped_records = []
        columns = list(df.columns)
        mapped = {k: _find_column(columns, names) for k, names in FIELD_ALIASES.items()}
        missing = [k for k in ("source_account", "destination_account", "amount", "timestamp") if not mapped[k]]
        if not mapped["transaction_id"] and not self.allow_derived_ids:
            missing.insert(0, "transaction_id (or --allow-derived-ids)")
        if missing:
            raise ValueError(f"Missing columns {missing}. Present CSV columns: {columns}")
        # Refuse to silently reinterpret a mixed/date-and-step dataset.
        if mapped["timestamp"] and df[mapped["timestamp"]].dropna().astype(str).str.strip().apply(
            lambda s: bool(NUMERIC.fullmatch(s))
        ).any() and (self.base_datetime is None or self.step_minutes is None):
            raise ValueError("Integer AMLSim timestamps detected: specify --base-date and --step-minutes; do not guess units")
        clean: List[CanonicalTransaction] = []
        labels: Dict[str, EvaluationLabel] = {}
        used_ids: set[str] = set()
        currencies: set[str] = set()
        derivation_count = 0
        for pos, (_, row) in enumerate(df.iterrows(), start=2):
            try:
                if mapped["transaction_id"]:
                    tx_id = _required_id(row[mapped["transaction_id"]])
                else:
                    tx_id = f"DERIVED-ROW-{pos:08d}"
                    derivation_count += 1
                if tx_id in used_ids:
                    raise ValueError("Duplicate transaction ID")
                src = _required_id(row[mapped["source_account"]])
                dst = _required_id(row[mapped["destination_account"]])
                amount = _parse_money(row[mapped["amount"]])
                raw_step = row[mapped["timestamp"]]
                if mapped["count"]:
                    count_raw = str(row[mapped["count"]]).strip()
                    if count_raw != "1":
                        raise ValueError("Aggregated tx_count != 1 cannot be treated as one transfer")
                if mapped["period_end"]:
                    if str(row[mapped["period_end"]]).strip() != str(raw_step).strip():
                        raise ValueError("Interval start/end differ; a single precise transfer time is unavailable")
                timestamp = parse_timestamp_to_iso(raw_step, self.base_datetime, self.step_minutes)
                cval = row[mapped["currency"]] if mapped["currency"] else ""
                currency = str(cval).strip().upper() if str(cval).strip() else self.default_currency
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    raise ValueError("Invalid/unknown currency code; use XXX when currency is not supplied")
                tx = CanonicalTransaction(transaction_id=tx_id, source_account=src,
                                          destination_account=dst, amount=amount,
                                          currency=currency, timestamp=timestamp)
                used_ids.add(tx_id)
                currencies.add(currency)
                clean.append(tx)
                if any(mapped[k] for k in ("is_sar", "source_alert_id", "source_alert_type")):
                    label = _parse_label(row[mapped["is_sar"]]) if mapped["is_sar"] else None
                    aid = str(row[mapped["source_alert_id"]]).strip() if mapped["source_alert_id"] else ""
                    kind = str(row[mapped["source_alert_type"]]).strip() if mapped["source_alert_type"] else ""
                    if label is not None or aid or kind:
                        labels[tx_id] = EvaluationLabel(transaction_id=tx_id, is_sar=label,
                                    source_alert_id=aid or None, source_alert_type=kind or None)
            except (ValueError, TypeError, OverflowError) as e:
                # IMPORTANT: no unredacted source rows or label-bearing metadata in API diagnostics.
                self.skipped_records.append({"row_index": pos, "reason": str(e)})
        if len(currencies) > 1:
            raise ValueError(f"Mixed currencies {sorted(currencies)} are unsupported: normalize currency before detection")
        self.audit = {
            "input_rows": len(df), "accepted_rows": len(clean), "rejected_rows": len(self.skipped_records),
            "distinct_accounts": len({acct for t in clean for acct in (t.source_account, t.destination_account)}),
            "source_transaction_ids_derived": derivation_count,
            "currency": next(iter(currencies)) if currencies else None,
            "currency_is_source_verified": bool(mapped["currency"]),
            "time_source_column": mapped["timestamp"],
            "step_minutes_explicitly_supplied": self.step_minutes is not None,
            "source_columns": columns,
            "evaluation_only_labels": len(labels),
        }
        logger.info("Accepted %s/%s rows, %s eval-only labels", len(clean), len(df), len(labels))
        return clean, labels

    def load_from_csv(self, path: str) -> Tuple[List[CanonicalTransaction], Dict[str, EvaluationLabel]]:
        # dtype=str preserves source account IDs with leading zeros, unlike pandas inference.
        return self.load_from_dataframe(pd.read_csv(path, dtype=str, keep_default_na=False))
