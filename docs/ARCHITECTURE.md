# DeclineDoctor Technical Architecture 🏗️

DeclineDoctor is an autonomous payments reliability, anomaly detection, and revenue recovery engine. It combines advanced statistical detection, deterministic causal diagnosis, constrained LLM narrative synthesis, and strict backend safety guardrails.

---

## High-Level Architecture Diagram

```
[ Transaction Event Stream / Configurable DB (SQLite / PostgreSQL) ]
                               │
                               ▼
                ┌──────────────────────────────┐
                │  Statistical Detection Engine│ (Z-score, p-value, 95% CI, EWMA)
                └──────────────┬───────────────┘
                               │ Creates Incident & Logs SHA-256 Audit Event
                               ▼
                ┌──────────────────────────────┐
                │  Causal Diagnosis Engine     │ (Dominant code, Confidence formula,
                └──────────────┬───────────────┘  Expanded decline taxonomy)
                               │
                ├──────────────┴───────────────┐
                ▼                              ▼
 ┌─────────────────────────────┐ ┌────────────────────────────────────────┐
 │ Advisory LLM Narrator       │ │ Strict Backend Policy & Guardrails     │
 │ (google.genai SDK +         │ │ - Confidence Gate (>= 0.70)            │
 │  Numeric Grounding          │ │ - Revenue Floor Gate (>= ₹50,000)      │
 │  Validator)                 │ │ - Auto-Approval Ceiling (<= ₹500,000)  │
 └──────────────┬──────────────┘ │ - Action Compatibility Matrix          │
                │                │ - Role-Based Access Control (RBAC)     │
                │                │ - Max Retry Budget Ceiling (<= 2)      │
                │                └──────────────────┬─────────────────────┘
                └───────────────────────────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ Counterfactual Action Engine │ (Evaluates REROUTE, ADJUST_TIMING,
                └──────────────┬───────────────┘  and SUPPRESS_RETRIES)
                               │
                               ▼
                ┌──────────────────────────────┐
                │ Payment Provider Abstraction │ (MockPaymentProvider for demo;
                │ & Recovery Execution         │  RazorpayPaymentProvider adapter)
                └──────────────┬───────────────┘
                               │
                ├──────────────┴───────────────┐
                ▼                              ▼
 ┌─────────────────────────────┐ ┌────────────────────────────────────────┐
 │ Cryptographic Audit Trail   │ │ Rollback & Safety Service              │
 │ (Append-Only SHA-256 Hash   │ │ (Reverts flipped transactions,         │
 │  Chained Verification)      │ │  restores baseline, logs proof)        │
 └─────────────────────────────┘ └────────────────────────────────────────┘
```

---

## 1. Data Models & Database Abstraction

Supported by SQLAlchemy ORM with thread-safe connection pooling and configurable `DATABASE_URL` (SQLite for local demo; PostgreSQL production compatible):

- **`Transaction`**: Raw payment records: `id`, `merchant_id`, `amount`, `timestamp`, `payment_method`, `issuer`, `card_network`, `decline_code`, `decline_reason`, `retry_count`, `routing_partner`, `success`.
- **`Incident`**: Tracks anomalies: `segment_issuer`, `segment_payment_method`, `window_start`, `window_end`, `baseline_success_rate`, `incident_success_rate`, `drop_pp`, `concentration_ratio`, `sample_size`, `state`, `severity`, `advanced_stats_json`.
- **`Diagnosis`**: Stores causal `hypothesis`, `confidence`, `dominant_decline_code`, `dominant_decline_code_share`, `evidence_json`, and advisory `narrative_text`.
- **`RecoveryAction`**: Records mitigation actions, selected actor, reasoning, `applied_at`, `approved_by`, `approved_at`, `role`, `is_rollback`, and `rolled_back_from_id`.
- **`Outcome`**: Quantifies post-intervention impact: `pre_success_rate`, `post_success_rate`, `recovered_revenue`, `transactions_flipped`, and `result`.
- **`AuditLog`**: Append-only, cryptographically sealed security log with `previous_hash` and `record_hash`.

---

## 2. Advanced Statistical Detection (`app/detection.py`)

Compares active window traffic against historical 14-day baselines:
1. **Two-Proportion Pooled Z-Test**:
   $$Z = \frac{p_1 - p_2}{\sqrt{p(1-p)\left(\frac{1}{n_1} + \frac{1}{n_2}\right)}}$$
2. **Two-Tailed P-Value**: Quantifies statistical significance ($p < 0.001$).
3. **95% Confidence Interval**:
   $$CI_{95\%} = (p_1 - p_2) \pm 1.96 \times SE$$
4. **Exponentially Weighted Moving Average (EWMA)**:
   $$EWMA_t = \alpha \cdot X_t + (1 - \alpha) \cdot EWMA_{t-1}, \quad \alpha = 0.3$$
5. **Concentration Ratio**: Segment failure volume relative to payment-method failure volume.

---

## 3. Causal Diagnosis & Decline Taxonomy (`app/diagnosis.py`)

Maps dominant decline patterns to causal hypotheses:
- **Routing / Network Issues** (`processor_declined`, `gateway_timeout`, `network_error`, `issuer_unavailable`) &rarr; `ROUTING_CONNECTIVITY_ISSUE`
- **Temporary BIN / Throttles** (`try_again_later`, `velocity_limit`) &rarr; `BIN_LEVEL_TEMPORARY_ISSUE`
- **Issuer Terminal Declines** (`insufficient_funds`, `do_not_honor`, `3ds_failure`, `authentication_failed`) &rarr; `ISSUER_SIDE_DECLINE`
- **Diffuse Noise** &rarr; `INSUFFICIENT_SIGNAL`

**Authoritative Confidence Formula:**
$$\text{Confidence} = 0.5 \times \text{Concentration} + 0.3 \times \text{Dominant Share} + 0.2 \times \min\left(\frac{\text{Sample Size}}{150}, 1.0\right)$$

---

## 4. Constrained LLM Advisory Subsystem (`app/llm_narrator.py`)

- Uses the official Google GenAI SDK (`google.genai`) with structured Pydantic schema generation (`ActionProposal`).
- **Numeric Grounding Validator**: Extracts all numbers from the narrative, excludes timestamps/dates/durations/identifiers/bullet items, and strictly reconciles all remaining numeric claims against structured evidence.
- **Deterministic Safe Fallback**: If LLM times out or is offline, the system falls back to rule-based generation without interruption.

---

## 5. Counterfactual Action Projections (`app/recovery_agent.py`)

For every diagnosed incident, DeclineDoctor calculates genuine projected outcomes across all candidate actions:
- `REROUTE` (42% effect size)
- `ADJUST_RETRY_TIMING` (21% effect size)
- `SUPPRESS_RETRIES` (0% effect size)
Evaluates projected transactions flipped, recovered revenue, projected post-intervention success rate, and domain compatibility.

---

## 6. Payment Provider Abstraction (`app/providers/`)

- Abstract contract `PaymentProvider` defines `reroute_traffic`, `adjust_retry_timing`, `suppress_retries`, `check_gateway_health`, and `rollback_reroute`.
- `MockPaymentProvider`: Deterministic sandbox provider for demo and automated regression testing.
- `RazorpayPaymentProvider`: Production adapter interface.
- Factory pattern ensures mock provider is active without exposing API keys.

---

## 7. Cryptographic Append-Only Audit Trail (`app/audit.py`)

Every lifecycle event is permanently recorded in an append-only SHA-256 hash chain:
$$H_i = \text{SHA-256}(H_{i-1} \parallel \text{Timestamp} \parallel \text{Actor} \parallel \text{EventType} \parallel \text{DetailsJSON})$$
Provides continuous tamper detection via `GET /api/incidents/{id}/audit/verify`.

---

---

## 9. Real-Time Payment Webhook Ingestion (`app/routes/webhooks.py`)

The platform implements production-grade HTTP webhook ingestion:
- **Pydantic Validation**: Strict schema enforcement (`PaymentWebhookPayload`) validating `event_id`, `payment_id`, `amount`, `currency`, `status`, `issuer`, `payment_method`, `card_bin`, `decline_code`, and `timestamp`.
- **Cryptographic Idempotency**: Persists webhook entries into `webhook_events` table indexed by `idempotency_key` and `payment_id`. Repeated payloads return HTTP 200 `DUPLICATE_ACCEPTED` with cached responses, preventing race conditions or duplicate anomaly counting.
- **Safety Invariant**: Webhook events enter the 9-stage pipeline with `auto_recover=False` strictly enforced. Webhooks **never** bypass policy gates or trigger unbounded automated mitigations.

---

## 10. Multi-Gateway Routing Intelligence (`app/providers/routing_optimizer.py`)

Transforms simple rerouting into a comprehensive multi-provider scoring optimizer:
- **Simulated Profiles**: Evaluates `Provider A`, `Provider B`, `Provider C`, and `Razorpay Smart Router` across success rates, P95 latencies, processing fees, availability health, and BIN/issuer affinities.
- **Composite Scoring Function**:
  $$\text{Score} = 0.40 \cdot S_{\text{success}} + 0.25 \cdot S_{\text{health}} + 0.15 \cdot S_{\text{latency}} + 0.10 \cdot S_{\text{cost}} + 0.10 \cdot S_{\text{BIN}} - P_{\text{degradation}}$$
- **Safety Boundary**: Operates in simulation/advisory mode (`LIVE_CALLS_ENABLED = False`). Does not move real funds.

---

## 11. Deep BIN-Level Intelligence (`app/bin_intelligence.py`)

Expands card-level observability to detect localized card range faults vs issuer-wide collapses:
- **Metrics Aggregation**: Tracks per-BIN volume, decline ratios, card networks, decline code distributions, and gateway dispersion.
- **Synthetic 3DS Authentication Failure Signal**: Models 3DS handshake failures per BIN without claiming access to real cardholder networks.
- **Isolation Diagnostic Verdict**: Formulates definitive isolation findings (e.g. `"Evidence indicates the incident is isolated to BIN 452114 rather than an issuer-wide decline pattern."`), enabling granular retry backoffs or issuer outreach rather than blanket routing switches.

---

## 12. 12-Factor Structured Causal Evidence (`app/diagnosis.py`)

Upgrades diagnostic explainability into an enterprise evidence payload:
1. `hypothesis`
2. `confidence`
3. `evidence_for` (supporting signals)
4. `evidence_against` (contradicting signals)
5. `key_statistical_signals` (z-score, p-value, drop_pp, EWMA, CUSUM)
6. `relevant_segment`
7. `provider_evidence`
8. `bin_evidence`
9. `recommended_action`
10. `why_appropriate`
11. `invalidation_criteria`
12. `uncertainty`

Internal reasoning tokens are strictly filtered out; only validated structured signals and conclusions are exposed to operators.

---


## 10. Production Architecture vs. Current Prototype 🌐

DeclineDoctor is architected with a strict separation between what is active in the current prototype/demo environment and what constitutes the target enterprise production deployment:

```
                      [ PRODUCTION ARCHITECTURE ]

  Razorpay Webhook / Kafka Payment Ingest Stream
                       │
                       ▼
  Streaming Event Bus (Apache Kafka / AWS Kinesis)
                       │ (Validates, Enriches with BIN/Bank metadata)
                       ▼
  Real-Time Feature Store & Evidence Aggregator
  (Hourly rolling baselines, CUSUM, EWMA, failure-code concentration)
                       │
                       ▼
  Statistical Anomaly Detection Pipeline
  (CUSUM + EWMA + Z-score deviation triggers incident lifecycle)
                       │
                       ▼
  Structured Evidence AI Diagnosis Subsystem
  (Structured evidence synthesis, supporting & contradicting signals)
                       │
                       ▼
  Authoritative Policy Gate (Deterministic Rules Engine)
  (Confidence >= 70%, Revenue checks, Dual-control human approval, RBAC)
                       │
                       ▼
  Smart Router & Provider Gateway Execution
  (Direct Razorpay Optimizer API, multi-gateway weights, intelligent backoff)
                       │
                       ▼
  Outcome Measurement & Cohort Telemetry
  (Calculates actual lift, flips recovered volume, measures latency)
                       │
                       ▼
  Closed-Loop Learning Loop
  (Records RecoveryLearning, updates Bayesian prior effectiveness, tunes ranking)
                       │
                       ▼
  Cryptographic Audit Chain & Production Observability
  (SHA-256 tamper-evident chain, Prometheus alerts, P95 stage latencies)
```

### Direct Comparison: Current Prototype vs. Production Design

| Component | Current Prototype (Verified) | Target Enterprise Production Design |
|---|---|---|
| **Payment Provider** | `MockPaymentProvider` (Deterministic sandbox) + `RazorpayPaymentProvider` (Test sandbox adapter with live mode strictly disabled) | Active Razorpay Smart Router & Optimizer APIs with redundant secondary PSP failovers |
| **Event Pipeline** | In-memory 9-stage pipeline trace simulator with realistic timestamps | Distributed streaming pipeline (Kafka/Flink) ingesting millions of webhook events/sec |
| **Financial Execution** | Bounded simulated transactions with retry ceilings ($\le 2$); real financial transactions strictly blocked | Direct gateway API dispatch with idempotency keys and merchant reconciliation |
| **Diagnosis Engine** | Numeric-grounded LLM advisory with deterministic fallback rule engine | Hybrid LLM + fine-tuned edge classifier with automated prompt caching |
| **Recovery Learning** | SQLite/PostgreSQL `recovery_learning` table tracking 38+ calibrated historical attempts | Distributed Bayesian bandit system updating dynamic gateway routing weights |
| **Experimentation** | Deterministic synthetic cohort simulations (100 txns/cohort, z-test) | Multi-armed bandit testing across canary traffic splits with live holdouts |
| **Audit Log** | Local SHA-256 parent-hash chained database table | Distributed immutable ledger (AWS QLDB or signed cloud storage WORM) |
| **Customer Safety** | Anonymized `CUST_XXXX` cooldown and retry limits without PII storage | Tokenized customer vault with Redis-backed distributed cooldown tokens |
