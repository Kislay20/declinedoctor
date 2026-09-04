# DeclineDoctor Product Specification 📋

## 1. Executive Summary

In global payment processing, silent decline spikes cost merchants and fintech platforms millions in lost revenue every month. Traditional monitoring alerts on gross failure spikes but leaves root-cause diagnosis, partner rerouting, and retry tuning to manual, slow human triage. Conversely, unrestrained autonomous agents risk making erroneous multi-million rupee routing changes without human oversight.

**DeclineDoctor** solves this by providing **Autonomous Diagnosis with Guardrailed Execution**:
- Real-time stream anomaly detection across segmented transaction flows.
- Transparent, deterministic root-cause diagnosis backed by numeric-grounded LLM narrative generation.
- Hard financial guardrails (minimum revenue floors, high-revenue human approval ceilings, retry budget caps).
- End-to-end auditability with persisted state and real recovery measurement.

---

## 2.1 Top-Level Revenue Recovery Funnel & Economics

DeclineDoctor visualizes revenue recovery through an end-to-end 7-stage conversion funnel:

```
PAYMENTS ➔ FAILED PAYMENTS ➔ REVENUE AT RISK ➔ DIAGNOSED ➔ RECOVERY ELIGIBLE ➔ RECOVERED ➔ NET RECOVERED
```

### Transparent Economic Formula & Cost Breakdown:
Every recovery intervention accounts for processing, gateway, retry, and cardholder friction costs:

$$\text{Net Recovered Revenue} = \text{Gross Recovered} - (\text{Gateway Fees} + \text{Retry Overhead} + \text{Customer Friction})$$
$$\text{ROI \%} = \frac{\text{Net Recovered Revenue}}{\text{Total Operational Costs}} \times 100$$

- **Gateway Processing Fees:** Standard 1.2% merchant interchange/routing fee.
- **Retry Surcharges:** ₹15.00 estimated fee per network retry probe.
- **Customer Friction Cost:** ₹5.00 estimated friction/churn risk penalty per retry attempt.
- **Strict Guardrail:** All cost assumptions are calibrated for enterprise Indian payments and transparently labeled with demo disclaimers.

---

## 3. Incident State Machine

```
              [ Stream Ingestion ]
                       │
                       ▼
             ┌──────────────────┐
             │ ANOMALY_DETECTED │
             └─────────┬────────┘
                       │
                       ▼  (diagnose_incident)
                 [ Confidence? ]
                  /          \
      < 0.70     /            \   >= 0.70
                ▼              ▼
     ┌──────────────────┐  ┌───────────┐
     │  ESCALATED_LOW_  │  │ DIAGNOSED │
     │    CONFIDENCE    │  └─────┬─────┘
     │   (Terminal)     │        │
     └──────────────────┘        ▼
                          [ At-Risk Revenue? ]
                          /        │         \
             < ₹50,000   /         │          \   > ₹500,000
                        ▼          │           ▼
           ┌─────────────────┐     │    ┌─────────────────────────┐
           │  ESCALATED_LOW_ │     │    │ AWAITING_HUMAN_APPROVAL │
           │     REVENUE     │     │    └────────────┬────────────┘
           │   (Terminal)    │     │                 │ (Human clicks approve)
           └─────────────────┘     │                 ▼
                                   │           [ APPROVED ]
                                   \                 /
                                    ▼               ▼
                                 ┌────────────────────┐
                                 │  ACTION_SELECTED   │
                                 └─────────┬──────────┘
                                           │
                                           ▼ (simulate & re-measure)
                                 [ Improvement >= 5pp? ]
                                   /                 \
                          No      /                   \  Yes
                                 ▼                     ▼
             ┌─────────────────────────────┐    ┌────────────┐
             │         ESCALATED_          │    │  RESOLVED  │
             │    INSUFFICIENT_RECOVERY    │    │ (Terminal) │
             │          (Terminal)         │    └────────────┘
             └─────────────────────────────┘
```

---

## 4. API Endpoints Specification

### 1. Dashboard Summary
- **Route**: `GET /api/dashboard/summary`
- **Response**:
```json
{
  "global_success_rate": 74.51,
  "active_incident_count": 1,
  "revenue_at_risk": 667325.06,
  "total_recovered_revenue": 107791.84
}
```

### 2. List Incidents
- **Route**: `GET /api/incidents`
- **Response**: Array of `Incident` objects ordered by `detected_at DESC`.

### 3. Incident Detail
- **Route**: `GET /api/incidents/{id}`
- **Response**:
```json
{
  "incident": { "id": "inc_...", "state": "DIAGNOSED", ... },
  "diagnosis": { "hypothesis": "ROUTING_CONNECTIVITY_ISSUE", "confidence": 0.73, ... },
  "recovery_action": { "action_type": "REROUTE", ... },
  "outcome": { "improvement_pp": 17.43, "recovered_revenue": 107791.84, ... }
}
```

### 4. Trigger Diagnosis
- **Route**: `POST /api/incidents/{id}/diagnose`
- **Behavior**: Deterministically scores confidence, generates LLM narrative with Gemini `gemini-2.5-flash`, respects terminal protection, and updates state.

### 5. Trigger Recovery
- **Route**: `POST /api/incidents/{id}/recover`
- **Request Body**:
```json
{
  "recommended_action": "REROUTE",
  "selected_by": "llm",
  "reasoning": "Reroute to Router_Beta to bypass BIN gateway failure",
  "human_approved": true
}
```
- **Response**:
```json
{
  "status": "RESOLVED",
  "outcome": {
    "improvement_pp": 18.71,
    "recovered_revenue": 272925.82,
    "resulting_success_rate": 76.71
  }
}
```

### 6. Incident Audit Trail
- **Route**: `GET /api/incidents/{id}/audit`
- **Response**: Chronologically sorted list of real audit logs from the database.

### 7. Demo Reset & Injection
- **Route**: `POST /api/simulate/inject`
- **Behavior**: Recreates tables, runs deterministic seeding, runs anomaly detection, and returns the number of incidents detected.

---

## 5. Non-Negotiable Guardrails & Policy Rules

1. **Allowed Actions**: `REROUTE`, `ADJUST_RETRY_TIMING`, `SUPPRESS_RETRIES`.
2. **Confidence Minimum**: $0.70$. No action permitted if confidence $< 0.70$.
3. **Revenue Floors & Ceilings**:
   - Minimum revenue for automated action: $₹50,000$.
   - Maximum revenue for automated execution without human approval: $₹500,000$.
4. **Retry Limit**: Max 2 retries per transaction.
5. **Terminal State Invariance**: `RESOLVED` and `ESCALATED_*` states can never be overwritten.
6. **LLM Boundary**: LLM produces natural language synthesis; backend enforces all thresholds, actions, and execution safety.

---

## 6. Buildathon Acceptance Criteria

| Scenario | Trigger Segment | Expected Confidence | At-Risk Revenue | Expected Terminal State | Expected Recovery |
|---|---|---|---|---|---|
| **Bank X / Card** | Bank X (452114) | $\ge 70\%$ ($\sim 73\%$) | $< ₹500\text{k}$ ($\sim ₹244\text{k}$) | `RESOLVED` | $\sim ₹107\text{k}$ recovered via `REROUTE` |
| **SBI / UPI** | SBI UPI | $< 70\%$ ($\sim 69\%$) | $< ₹500\text{k}$ ($\sim ₹171\text{k}$) | `ESCALATED_LOW_CONFIDENCE` | None (Action blocked by confidence gate) |
| **ICICI / Card** | ICICI (476543) | $\ge 70\%$ ($\sim 71\%$) | $> ₹500\text{k}$ ($\sim ₹667\text{k}$) | `RESOLVED` (after human approval) | $\sim ₹272\text{k}$ recovered after human approval |
