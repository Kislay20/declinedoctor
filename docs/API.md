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

### `GET /incidents/{id}/audit`
Retrieves chronological audit trail for the incident.

### `GET /incidents/{id}/audit/verify`
Performs cryptographic SHA-256 hash-chain verification over all audit records for this incident.

---

## 3. Simulation & Event Streaming

### `POST /simulate/inject`
Seeds fresh demo data and runs initial anomaly detection.

### `POST /simulate/recovery`
Sandbox execution of genuine recovery mathematics across arbitrary inputs (issuer, volume, failure rate, average ticket, hypothesis, action).

### `POST /simulate/stream`
Ingests a live transaction event through the continuous monitoring pipeline (`Transaction Event -> Detection -> Diagnosis -> Policy -> Recovery -> Measurement`).

---

## 4. Analytics & Evaluation

### `GET /segments/analytics`
Granular segment performance breakdown filterable by `issuer`, `payment_method`, and `decline_code`.

### `GET /evaluation`
Runs model benchmark over the 60 ground-truth scenarios and returns Precision, Recall, F1 Score, FPR, FNR, and Confusion Matrix.

### `GET /observability`
Telemetry report including database connectivity, audit chain integrity, processing throughput, error counts, and latency percentiles.

### `GET /health`
System liveness check (`status: ok`).
