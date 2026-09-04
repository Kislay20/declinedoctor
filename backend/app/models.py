from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from datetime import datetime
from .database import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, index=True)
    merchant_id = Column(String, index=True)
    amount = Column(Float)
    timestamp = Column(DateTime, index=True)
    payment_method = Column(String)  # card/upi/netbanking/wallet
    issuer = Column(String, index=True)
    card_network = Column(String)
    decline_code = Column(String)
    decline_reason = Column(String)
    retry_count = Column(Integer, default=0)
    customer_id = Column(String)
    routing_partner = Column(String)
    success = Column(Boolean)

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(String, primary_key=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    segment_issuer = Column(String)
    segment_payment_method = Column(String)
    window_start = Column(DateTime)
    window_end = Column(DateTime)
    baseline_success_rate = Column(Float)
    incident_success_rate = Column(Float)
    drop_pp = Column(Float)
    concentration_ratio = Column(Float)
    sample_size = Column(Integer)
    state = Column(String) # lifecycle/guardrail states including human-approval and escalation terminals

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    
    id = Column(String, primary_key=True, index=True)
    incident_id = Column(String, ForeignKey("incidents.id"))
    hypothesis = Column(String)
    confidence = Column(Float)
    dominant_decline_code = Column(String)
    dominant_decline_code_share = Column(Float)
    evidence_json = Column(Text)
    narrative_text = Column(Text)

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"
    
    id = Column(String, primary_key=True, index=True)
    incident_id = Column(String, ForeignKey("incidents.id"))
    action_type = Column(String) # REROUTE, ADJUST_RETRY_TIMING, SUPPRESS_RETRIES
    selected_by = Column(String) # llm | deterministic_fallback
    reasoning_text = Column(Text)
    applied_at = Column(DateTime, default=datetime.utcnow)

class Outcome(Base):
    __tablename__ = "outcomes"
    
    id = Column(String, primary_key=True, index=True)
    recovery_action_id = Column(String, ForeignKey("recovery_actions.id"))
    pre_success_rate = Column(Float)
    post_success_rate = Column(Float)
    recovered_revenue = Column(Float)
    transactions_flipped = Column(Integer)
    result = Column(String) # resolved | escalated_insufficient | escalated_low_confidence

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    actor = Column(String) # system | llm | human
    event_type = Column(String)
    details_json = Column(Text)