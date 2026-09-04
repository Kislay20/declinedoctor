# DeclineDoctor Technical Architecture 🏗️

DeclineDoctor is an autonomous payments reliability and revenue recovery platform. It bridges statistical stream anomaly detection with deterministic expert systems, constrained LLM narrative synthesis, and strict financial guardrails.

---

## High-Level Architecture Diagram

```
[ Transaction Stream / SQLite Database ]
                    │
                    ▼
       ┌─────────────────────────┐
       │ Anomaly Detection Engine│  (14-Day Baseline vs 2-Hour Window)
       └────────────┬────────────┘
                    │  Creates Incident & ANOMALY_DETECTED AuditLog
                    ▼
       ┌─────────────────────────┐
       │ Deterministic Diagnosis │  (Root-cause mapping & Confidence scoring)
       └────────────┬────────────┘
                    ├──────────────────────────┐
                    ▼                          ▼
       ┌─────────────────────────┐ ┌───────────────────────────┐
       │ Advisory LLM Narrator   │ │ Backend Safety Guardrails │
       │ (Gemini 2.5 Flash +     │ │ - Confidence Gate (>=0.70)│
       │  Numeric Grounding)     │ │ - Auto-Action Min (>=₹50k)│
       └────────────┬────────────┘ │ - Human Approval (>₹500k) │
                    │              │ - Terminal State Lock     │
                    │              └─────────────┬─────────────┘
                    └────────────────────────────┘
                                   │
                                   ▼
                      ┌─────────────────────────┐
                      │ Recovery Action Engine  │
                      │ (Simulation & Retries)  │
                      └────────────┬────────────┘
                                   │
                                   ▼
                      ┌─────────────────────────┐
                      │  Outcome & Audit Trail  │
                      │  (SQLite Real AuditLog) │
                      └─────────────────────────┘
```

---

## 1. Data Models & Persistence

The backend utilizes SQLite via SQLAlchemy ORM with thread-safe connection pooling:

- **`Transaction`**: Raw payment records containing `id`, `merchant_id`, `amount`, `timestamp`, `payment_method`, `issuer`, `card_network`, `decline_code`, `decline_reason`, `retry_count`, `routing_partner`, and `success`.
- **`Incident`**: Tracks anomalies with `segment_issuer`, `segment_payment_method`, `window_start`, `window_end`, `baseline_success_rate`, `incident_success_rate`, `drop_pp`, `concentration_ratio`, `sample_size`, and `state`.
- **`Diagnosis`**: Stores the root-cause `hypothesis`, `confidence`, `dominant_decline_code`, `dominant_decline_code_share`, `evidence_json`, and advisory `narrative_text`.
- **`RecoveryAction`**: Records actions (`REROUTE`, `ADJUST_RETRY_TIMING`, `SUPPRESS_RETRIES`), execution actor (`system` / `llm`), reasoning, and timestamp.
- **`Outcome`**: Quantifies post-intervention impact: `improvement_pp`, `recovered_revenue`, and `resulting_success_rate`.
- **`AuditLog`**: Tamper-proof, append-only security log recording every lifecycle transition: `timestamp`, `actor`, `event_type`, and `details_json`.

---

## 2. Anomaly Detection Engine (`app/detection.py`)

1. **Window Aggregation**: Evaluates transactions in the active incident window ($t - 2\text{ hours}$ to $t$) and compares them to a historical 14-day baseline.
2. **Segmentation**: Slices traffic by `(issuer, payment_method)`.
3. **Drop Calculation**: Computes percentage-point drop:
   $$\text{Drop}_{\text{pp}} = (\text{Baseline Success Rate} - \text{Incident Success Rate}) \times 100$$
4. **Concentration Ratio**: Computes the segment's share of total method-wide failures:
   $$\text{Concentration} = \frac{\text{Failures}_{\text{segment}}}{\text{Failures}_{\text{payment\_method}}}$$
5. **Threshold Trigger**: Triggers an incident when $\text{Drop}_{\text{pp}} \ge 15.0$ and $\text{Sample Size} \ge 20$.
6. **Audit Event**: Emits `ANOMALY_DETECTED` into the database.

---

## 3. Deterministic Diagnosis Engine (`app/diagnosis.py`)

1. **Dominant Decline Analysis**: Determines the highest-frequency decline reason in the incident window.
2. **Hypothesis Mapping**:
   - `processor_declined` / `gateway_timeout` $\rightarrow$ `ROUTING_CONNECTIVITY_ISSUE`
   - `try_again_later` $\rightarrow$ `BIN_LEVEL_TEMPORARY_ISSUE`
   - `insufficient_funds` / `do_not_honor` $\rightarrow$ `ISSUER_SIDE_DECLINE`
   - Unrecognized / diffuse codes $\rightarrow$ `INSUFFICIENT_SIGNAL`
3. **Confidence Scoring Formula**:
   $$\text{Confidence} = 0.5 \times \text{Concentration} + 0.3 \times \text{Dominant Share} + 0.2 \times \min\left(\frac{\text{Sample Size}}{150}, 1.0\right)$$
4. **Confidence Gate**:
   - If $\text{Confidence} < 0.70$: Marks incident as `ESCALATED_LOW_CONFIDENCE`, emits `ESCALATION` audit log, and blocks automated action.
   - If $\text{Confidence} \ge 0.70$: Transitions incident to `DIAGNOSED`.
5. **Terminal Protection**: If incident is already in a terminal state, skips re-diagnosis and preserves terminal state.
6. **Idempotency**: Reuses existing `Diagnosis` row to prevent duplicate database rows.

---

## 4. Constrained LLM Advisory Subsystem (`app/llm_narrator.py`)

1. **Model**: Powered by Google Gemini `gemini-2.5-flash` with structured Pydantic schema generation (`ActionProposal`).
2. **Numeric Grounding Validator (`_validate_narrative_numbers`)**:
   - Extracts all numbers from the LLM narrative.
   - Allows calendar formatting, dates (`2026-09-04`), hours/minutes (`14:00`), list items (`1.`, `2.`), and small integers ($\le 4$).
   - Reconciles every statistical or financial number (percentages, sample sizes, currency values) against `evidence_json`.
   - Rejects ungrounded or hallucinated claims.
3. **Deterministic Fallback**: If LLM API fails, times out, or hallucinates numbers, the system automatically falls back to deterministic rule-based proposals without crashing.

---

## 5. Recovery Simulation & Safety Guardrails (`app/recovery_agent.py`)

The backend is the sole authority for financial safety and execution:

1. **Terminal Check**: Rejects any actions on terminal incidents (`RESOLVED`, `ESCALATED_*`).
2. **Confidence Check**: Re-verifies confidence $\ge 0.70$.
3. **At-Risk Revenue Gate**:
   - If At-Risk $< ₹50,000$: Transitions to `ESCALATED_LOW_REVENUE`.
   - If At-Risk $> ₹500,000$ and `human_approved` is `False`: Holds incident in `AWAITING_HUMAN_APPROVAL`, emits `HUMAN_APPROVAL_REQUIRED` audit event, and immediately halts execution.
4. **Retry Budget Hard Ceiling**: Strictly caps simulated retries to $\le 2$ per transaction.
5. **Action Simulation**:
   - `REROUTE`: Simulates routing through alternate partner (`Router_Beta`), converting eligible failures to success.
   - `ADJUST_RETRY_TIMING`: Simulates backoff retry intervals.
   - `SUPPRESS_RETRIES`: Blocks futile retries to preserve customer balance and avoid fee penalties.
6. **Outcome Threshold**: Verifies measurable improvement $\ge 5.0$ percentage points. If $< 5.0$ pp, marks `ESCALATED_INSUFFICIENT_RECOVERY`.

---

## 6. Audit Trail & Immutability (`AuditLog`)

All state changes are permanently logged to SQLite:
- `ANOMALY_DETECTED` (at detection time)
- `DIAGNOSED` (at diagnosis time)
- `ESCALATION` (for low confidence or low revenue)
- `HUMAN_APPROVAL_REQUIRED` (when revenue exceeds ₹500,000)
- `ACTION_SELECTED` (when recovery action is chosen)
- `OUTCOME_MEASURED` (when recovery simulation succeeds)
- `RECOVERY_BLOCKED` (when terminal state or guardrails reject action)

---

## 7. Frontend Interface (`frontend/src/`)

- Built with **React 18** and **Vite**, styled with clean, responsive dark-mode aesthetics using Tailwind utility classes and Lucide icons.
- **`Dashboard.jsx`**: Real-time KPI cards (Global Success Rate, Active Incidents, Revenue at Risk, Recovered Revenue), Active vs Historical incident tabs, and a one-click Demo Reset / Re-seed action.
- **`IncidentView.jsx`**: Deep-dive triage view showing evidence breakdown, dominant decline distribution, advisory LLM narrative, human approval interactive card, and simulated recovery outcomes.
- **`AuditTrail.jsx`**: Real-time chronological audit trail loaded directly from the backend database.
