"""DeclineDoctor Payment Event Ingestion Webhook.

Provides production-grade webhook ingestion with strict Pydantic payload validation,
idempotency protection against duplicate event delivery, and integration into the
controlled 9-stage monitoring pipeline without triggering unbounded financial recovery.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Transaction, WebhookEvent, Incident
from ..streaming import process_transaction_event

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


class PaymentWebhookPayload(BaseModel):
    """Pydantic schema for validating incoming payment event payloads."""
    model_config = ConfigDict(extra="ignore")

    payment_id: str = Field(..., min_length=3, max_length=128, description="Unique payment or transaction ID")
    amount: float = Field(..., gt=0, description="Payment amount (must be positive)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 Currency Code")
    status: str = Field(..., description="Payment state (captured, failed, authorized, success)")
    issuer: str = Field(..., min_length=1, max_length=64, description="Card issuer or bank name")
    payment_method: str = Field(..., min_length=1, max_length=32, description="card, upi, netbanking, or wallet")
    card_bin: Optional[str] = Field(default=None, max_length=16, description="6-to-8 digit Bank Identification Number")
    card_network: Optional[str] = Field(default=None, max_length=32, description="Visa, Mastercard, RuPay, etc.")
    decline_code: Optional[str] = Field(default=None, max_length=64, description="Decline or error code if failed")
    decline_reason: Optional[str] = Field(default=None, max_length=256, description="Human-readable decline message")
    timestamp: Optional[str] = Field(default=None, description="ISO 8601 creation timestamp")
    provider: Optional[str] = Field(default="Razorpay Smart Router", max_length=64, description="Payment gateway or provider")
    merchant_id: Optional[str] = Field(default="m_default", max_length=64, description="Merchant account identifier")
    retry_count: Optional[int] = Field(default=0, ge=0, le=10, description="Current retry attempt number")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Client idempotency key")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary metadata attributes")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().lower()
        valid = {"captured", "failed", "authorized", "success", "declined", "pending"}
        if clean not in valid:
            raise ValueError(f"Invalid payment status '{v}'. Must be one of {sorted(valid)}")
        return clean

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        return round(v, 2)


@router.post("/payment", status_code=status.HTTP_200_OK)
def ingest_payment_webhook(
    payload: PaymentWebhookPayload,
    x_idempotency_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Ingest real-time payment event into the controlled 9-stage pipeline.

    - Validates payload structure and fields via Pydantic.
    - Strictly enforces idempotency using idempotency_key or payment_id.
    - Never executes automated financial actions directly from webhooks.
    """
    effective_idempotency_key = (
        payload.idempotency_key
        or x_idempotency_key
        or f"idem_{payload.payment_id}"
    )

    # 1. Idempotency Check
    existing_webhook = (
        db.query(WebhookEvent)
        .filter(
            (WebhookEvent.idempotency_key == effective_idempotency_key)
            | (WebhookEvent.payment_id == payload.payment_id)
        )
        .first()
    )

    if existing_webhook:
        stored_response = {}
        if existing_webhook.response_json:
            try:
                stored_response = json.loads(existing_webhook.response_json)
            except Exception:
                pass
        return {
            "status": "DUPLICATE_ACCEPTED",
            "message": "Payment event already ingested idempotently; skipped duplicate processing.",
            "payment_id": payload.payment_id,
            "idempotency_key": effective_idempotency_key,
            "is_duplicate": True,
            "original_received_at": existing_webhook.received_at.isoformat() if existing_webhook.received_at else None,
            "pipeline_trace": stored_response.get("pipeline_trace", []),
            "lifecycle_stage": stored_response.get("lifecycle_stage", "IDEMPOTENT_DUPLICATE"),
        }

    # Normalize Timestamp
    event_timestamp = None
    if payload.timestamp:
        try:
            event_timestamp = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
        except Exception:
            event_timestamp = datetime.now()
    else:
        event_timestamp = datetime.now()

    is_success = payload.status in {"captured", "success", "authorized"}

    # Prepare streaming event dictionary
    stream_event = {
        "id": payload.payment_id,
        "amount": payload.amount,
        "currency": payload.currency,
        "issuer": payload.issuer,
        "payment_method": payload.payment_method,
        "bin": payload.card_bin,
        "card_network": payload.card_network,
        "gateway": payload.provider or "Razorpay Smart Router",
        "success": is_success,
        "decline_code": payload.decline_code if not is_success else None,
        "decline_reason": payload.decline_reason if not is_success else None,
        "retry_count": payload.retry_count or 0,
        "timestamp": event_timestamp.isoformat(),
        "merchant_id": payload.merchant_id,
        "auto_recover": False,  # WEBHOOKS NEVER DIRECTLY EXECUTE FINANCIAL ACTIONS
        "auto_execute": False,
    }

    # 2. Process through controlled 9-stage pipeline
    pipeline_result = process_transaction_event(
        db=db,
        event=stream_event,
        auto_recover=False,  # Enforce safety: no direct financial execution
        user_role="OPERATOR",
    )

    # 3. Persist Webhook Event Record for idempotency
    webhook_rec = WebhookEvent(
        id=f"wbk_{uuid.uuid4().hex[:12]}",
        payment_id=payload.payment_id,
        idempotency_key=effective_idempotency_key,
        received_at=datetime.now(),
        payload_json=json.dumps(payload.model_dump(mode="json")),
        status="PROCESSED",
        response_json=json.dumps(pipeline_result),
    )
    db.add(webhook_rec)
    db.commit()

    return {
        "status": "PROCESSED",
        "payment_id": payload.payment_id,
        "idempotency_key": effective_idempotency_key,
        "is_duplicate": False,
        "pipeline_result": pipeline_result,
        "lifecycle_stage": pipeline_result.get("lifecycle_stage"),
        "safety_check": pipeline_result.get("safety_check"),
        "incident_id": pipeline_result.get("incident_id"),
    }
