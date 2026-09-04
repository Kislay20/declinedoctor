# DeclineDoctor API Reference 📡

Base URL: `http://localhost:8000/api`

---

## 1. Dashboard & Operations

### `GET /dashboard/summary`
Returns global 24h success rate, active incident counts, revenue at risk, total recovered revenue, recovery rate percentage, recovery funnel metrics, and the human approval queue.

**Response Example:**
```json
{
  "global_success_rate": 74.51,
  "active_incident_count": 0,
  "revenue_at_risk": 0.0,
  "total_recovered_revenue": 380717.66,
  "recovery_rate_pct": 54.14,
  "transactions_affected": 67,
  "actions_executed": 2,
  "escalated_incidents": 1,
  "stopped_incidents": 3,
  "human_approvals_granted": 1,
  "average_recovery_improvement_pp": 18.07,
  "funnel": {
    "at_risk": 703160.25,
    "diagnosed": 703160.25,
    "eligible": 531380.47,
    "recovered": 380717.66
  },
  "approval_queue": []
}
```

---

## 2. Incident Management

### `GET /incidents`
Returns list of all incidents with backend-calculated at-risk revenue and status.

### `GET /incidents/{id}`
Returns incident details, diagnosis, recovery action, and measured outcome.

### `POST /incidents/{id}/diagnose`
Triggers deterministic hypothesis classification, confidence calculation, and LLM narrative synthesis with numeric grounding validation.

### `POST /incidents/{id}/recover`
Applies bounded recovery action. Validates confidence (&ge; 0.70), revenue floor (&ge; ₹50k), auto-approval ceiling (&le; ₹500k), action compatibility, and role permissions.
- **Headers:** `X-User-Role: ADMIN | OPERATOR | ANALYST | VIEWER`
- **Request Body:**
  ```json
  {
    "recommended_action": "REROUTE",
    "selected_by": "system",
    "human_approved": false,
    "role": "OPERATOR"
  }
  ```

### `GET /incidents/{id}/counterfactuals`
Returns genuine projected outcomes across all 3 candidate actions (`REROUTE`, `ADJUST_RETRY_TIMING`, `SUPPRESS_RETRIES`).

### `GET /incidents/{id}/explanation`
Generates structured answers explaining:
- `why_did_declinedoctor_act`
- `why_did_declinedoctor_not_act`
- `why_did_declinedoctor_stop`
- `why_is_human_approval_required`

### `GET /incidents/{id}/safety`
Evaluates all safety gates and returns overall policy status (`SAFE_TO_EXECUTE`, `HUMAN_APPROVAL_REQUIRED`, `AUTOMATED_RECOVERY_BLOCKED`).

### `POST /incidents/{id}/rollback`
Reverts applied recovery, restores original failed transaction statuses, and transitions incident to `ROLLED_BACK`. Requires `ADMIN` or `OPERATOR` role.

### `GET /incidents/feed`
Returns structured real-time activity feed of active payment anomalies with severity, issuer, payment rail, revenue at risk, success rate drop, diagnosis hypothesis, policy state, recommended action, and approval requirement.

### `POST /incidents/{id}/reject`
Dual-control rejection of a proposed recovery action for high-value or escalated incidents.
- **RBAC**: Requires `ADMIN` or `OPERATOR` role (`can_approve_recovery`).
- **State Transition**: Transitions incident to `APPROVAL_REJECTED` (terminal state).
- **Audit**: Seals cryptographic SHA-256 audit record `APPROVAL_REJECTED`.

---

## 3. Webhook Ingestion & Event Pipeline

### `POST /webhooks/payment`
Production-grade payment event webhook ingestion endpoint. Validates incoming payment telemetry with Pydantic, guarantees strict idempotency, and enters the 9-stage event pipeline (`RECEIVED -> VALIDATED -> SEGMENTED -> ANOMALY_CHECKED -> DIAGNOSED -> POLICY_EVALUATED -> ACTION_SELECTED -> ACTION_APPLIED -> OUTCOME_MEASURED`).
- **Safety Invariant**: Webhooks enter the pipeline with `auto_recover=False` by default. Webhooks **never** trigger unbounded automated recovery.
- **Payload Fields**:
  ```json
  {
    "event_id": "evt_abc123",
    "payment_id": "pay_xyz789",
    "amount": 2500.0,
    "currency": "INR",
    "status": "failed",
    "issuer": "Bank X",
    "payment_method": "card",
    "card_bin": "452114",
    "decline_code": "processor_declined",
    "decline_reason": "Routing partner connectivity degradation",
    "provider": "Provider A",
    "idempotency_key": "idem_12345678",
    "metadata": {}
  }
  ```
- **Idempotency**: Duplicate payment events within the idempotency window return HTTP 200 `DUPLICATE_ACCEPTED` with cached response, preventing redundant processing.

---

## 4. Multi-Gateway Routing Intelligence

### `GET /providers/profiles`
Returns operational profiles for all registered simulated payment gateways (`Provider A`, `Provider B`, `Provider C`, `Razorpay Smart Router`), including success rate, latency, fee cost %, health state, and BIN/issuer specialization.

### `GET /providers/routing/recommendation`
Scores and ranks payment gateways for a specific issuer, payment method, and BIN.
- **Query Parameters**: `issuer`, `payment_method`, `bin`, `decline_reason`.
- **Scoring Dimensions**:
  - Success probability ($40\%$)
  - Health & availability ($25\%$)
  - Latency ($15\%$)
  - Processing cost ($10\%$)
  - BIN/segment affinity ($10\%$)
  - Degradation penalties (e.g., $-25$ for gateway timeouts)
- **Safety Guarantee**: Multi-gateway optimizer is strictly in simulation/advisory mode (`LIVE_CALLS_ENABLED = False`). Does not bypass policy guardrails.

### `POST /providers/routing/score`
Probe endpoint to score gateways dynamically against custom telemetry inputs.

---

## 5. Segment & BIN Intelligence

### `GET /segments/analytics`
Granular segment performance breakdown filterable by `issuer`, `payment_method`, and `decline_code`.

### `GET /segments/bin-intelligence`
Deep BIN-level intelligence and anomaly isolation diagnostic engine.
- **Query Parameters**: `issuer`, `payment_method`, `bin`.
- **Metrics**: Aggregated transaction volume, decline rate, decline code distribution, provider dispersion, and synthetic 3DS authentication failure signal.
- **Isolation Diagnostic Verdict**: Detects whether an incident is concentrated on an isolated BIN range (e.g. `"Evidence indicates the incident is isolated to BIN 452114 rather than an issuer-wide decline pattern."`) versus an issuer-wide rail outage.

---

## 6. Simulation & Event Streaming

### `POST /simulate/inject`
Seeds fresh demo data and runs initial anomaly detection.

### `POST /simulate/recovery`
Sandbox execution of genuine recovery mathematics across arbitrary inputs (issuer, volume, failure rate, average ticket, hypothesis, action).

### `POST /simulate/stream_event`
Ingests a single transaction event through the 9-stage monitoring pipeline.

### `GET /simulate/customers`
Returns demo customer profiles with retry caps, friction scores, and cooldown safety states (anonymized `CUST_XXXX`).

---

## 7. Model Evaluation & Observability

### `GET /evaluation`
Runs model benchmark over the 60 ground-truth scenarios (or 210 enterprise scenarios if `?expanded=true`) and returns Precision, Recall, F1 Score, Confusion Matrix, safety metrics, and zero-unsafe-action proofs.

### `GET /observability`
Telemetry report including database connectivity, audit chain integrity, processing throughput, error counts, latency percentiles, and stage latencies.

### `GET /observability/alerts`
Live evaluation of 5 production alert rules: Provider health degradation, High recovery failure rate, Unusual escalation spike, Model confidence degradation, and Recovery rollback spike.

---

## 8. Learning & Experiments

### `GET /learning/summary`
Global recovery learning summary (historical attempts, global effectiveness %, per-action effectiveness, and dynamic recommendation ranking).

### `GET /learning/effectiveness`
Calculates empirical historical effectiveness, average lift, and confidence modifier for a proposed candidate action.

### `GET /experiments/summary`
Deterministic offline A/B cohort experiment comparing two recovery actions across 100 failed transactions (sample size, lift, net revenue, friction score, and two-proportion z-test p-value).

### `POST /experiments/run`
Runs custom offline cohort experiment with configurable actions, sample size, and segment ticket sizes. Deterministic RNG seeded via SHA-256 ensures identical inputs produce identical outputs across process restarts.

### `GET /health`
System liveness check (`status: ok`).

