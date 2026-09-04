# DeclineDoctor 🩺💳

### Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery

> **Autonomous, Guardrail-First Payment Decline Diagnosis & Safe Revenue Recovery Platform**

**Diagnose the failure. Prescribe the fix. Prove the recovery.**

---

## 📌 The Problem

Payment failures create revenue at risk in real time, but blindly retrying every failed payment is not a safe recovery strategy. Repeated retries can increase customer friction, processor costs, and issuer-side blocking, while cryptic decline signals make root-cause diagnosis difficult.

Merchant operations teams need to answer four questions quickly:
- **Why did payment success rate suddenly drop?**
- **Which issuer/BIN/payment rail is responsible?**
- **Is the failure actually recoverable?**
- **What intervention can recover revenue without violating safety constraints?**

---

## 💡 The Solution

DeclineDoctor is an AI revenue-recovery agent that operates across a closed-loop lifecycle:

```
DETECT ➔ EVIDENCE ➔ DIAGNOSE ➔ CONFIDENCE GATE ➔ ACTION DECISION ➔ HUMAN APPROVAL GATE ➔ RECOVERY SIMULATION ➔ RE-MEASURE ➔ RECOVERED REVENUE ➔ TERMINAL STATE ➔ AUDIT PROOF
```

DeclineDoctor continuously monitors payment transaction streams, detects anomalous failure spikes across card and payment method segments, conducts deterministic root-cause diagnosis backed by numeric-grounded LLM narrative synthesis, enforces strict financial guardrails and human-in-the-loop approvals, executes safe recovery simulations, and records append-only, SHA-256 tamper-proof audit trails.

> **"The AI proposes and explains. Backend policy decides."**

### 🎯 Track Focus & Direction
- **Event**: Razorpay AI Buildathon 2026
- **Track**: Track 03 — AI Revenue Recovery
- **Direction**: Payment degradation ➔ Root-cause diagnosis ➔ Bounded safe recovery intervention

---

## 🎯 Core Intended Lifecycle

1. **DETECT**: Statistical anomaly detection evaluates success rate drops against 14-day rolling baselines using pooled two-proportion Z-tests, p-values, 95% confidence intervals, and hourly EWMA.
2. **EVIDENCE**: Collects failure concentration ratios, transaction volume, and dominant decline codes from actual logs.
3. **DIAGNOSE**: Deterministic causal classification maps decline codes to hypotheses and calculates confidence:
   $$\text{Confidence} = 0.5 \times \text{Concentration} + 0.3 \times \text{Dominant Share} + 0.2 \times \min\left(\frac{\text{Sample Size}}{150}, 1.0\right)$$
4. **CONFIDENCE GATE**: Confidence $\ge 0.70$ is mandatory. If confidence $< 0.70$, the incident transitions immediately to `ESCALATED_LOW_CONFIDENCE` with an `ESCALATION` audit log and automated action is blocked.
5. **ACTION DECISION**: Evaluates counterfactual outcomes across `REROUTE`, `ADJUST_RETRY_TIMING`, and `SUPPRESS_RETRIES`. Advisory LLM summaries are generated via the official `google.genai` SDK with strict numeric grounding verification.
6. **HUMAN APPROVAL GATE**: If at-risk revenue exceeds ₹500,000, automated execution is blocked. The incident enters `AWAITING_HUMAN_APPROVAL`, requiring authorization from an `ADMIN` or `OPERATOR` role.
7. **RECOVERY SIMULATION**: Safely tests the recovery action against failed transactions (strictly capped at $\le 2$ retries per transaction) and verifies minimum measurable improvement ($\ge 5.0$ percentage points).
8. **RE-MEASURE & REVENUE**: Calculates actual recovered revenue from recovered transactions.
9. **TERMINAL STATE PROTECTION**: Terminal states (`RESOLVED`, `ESCALATED_LOW_CONFIDENCE`, `ESCALATED_INSUFFICIENT_RECOVERY`, `ESCALATED_LOW_REVENUE`, `ROLLED_BACK`, `APPROVAL_REJECTED`) are strictly immutable.
10. **CRYPTOGRAPHIC AUDIT PROOF**: Every lifecycle change is permanently recorded in a SHA-256 parent-hash chained audit log, independently verifiable for tamper detection.

---

## 🛡️ Non-Negotiable Safety Guardrails

| Guardrail | Threshold / Policy | Backend Enforcement |
|---|---|---|
| **Live Calls Safety** | `LIVE_CALLS_ENABLED = False` | Strictly disabled; zero live financial exposure; no real money moved |
| **Razorpay Integration** | Sandbox / Adapter Mode | Uses test/simulation provider contracts (`is_live = False`); never executes live charges |
| **Confidence Gate** | $\ge 0.70$ (70%) | Incidents $< 0.70$ transition to `ESCALATED_LOW_CONFIDENCE`; auto-recovery blocked |
| **Minimum Revenue for Action** | $\ge ₹50,000$ | Immaterial incidents ($< ₹50,000$) escalate to `ESCALATED_LOW_REVENUE` |
| **Human Approval Cap** | $> ₹500,000$ | Automatically holds in `AWAITING_HUMAN_APPROVAL` pending dual-control authorization |
| **Retry Budget Cap** | $\le 2$ retries/txn | Hard ceiling enforced in recovery simulation; protects cardholder experience |
| **Measurable Threshold** | $\ge 5.0$ pp improvement | Below 5 pp escalates to `ESCALATED_INSUFFICIENT_RECOVERY` |
| **Terminal State Invariance** | Immutable | Terminal incidents reject repeated diagnosis, recovery execution, or tampering |
| **Role-Aware Access Control** | ADMIN / OPERATOR | Unauthorized roles (`VIEWER`, `ANALYST`) blocked from financial or approval actions |
| **LLM Execution Authority** | Zero execution rights | LLM cannot execute tools or mutate DB state; backend policy remains sole authority |
| **Webhook Ingestion Safety** | `auto_recover = False` | Ingesting payment webhooks never triggers automatic financial execution |

---

## 🤖 Role of AI & Deterministic Fallback

- **Grounded LLM Narrative Synthesis**: DeclineDoctor utilizes Google Gemini (`gemini-2.5-flash` via the official `google.genai` SDK) to translate structured mathematical decline evidence into clear operational narratives for human-in-the-loop operators.
- **Pydantic Validation & Numeric Spot-Checking**: All LLM outputs are validated against strict Pydantic schemas (`ActionProposal`). A backend regex validator strips non-numeric tokens and confirms every number cited in the narrative matches actual observed evidence; any unsupported numeric claim is rejected at the trust boundary.
- **Deterministic Fallback**: The system does not depend on an LLM being available for core safety or decisioning. If Gemini is unavailable, rate-limited (429), unconfigured, or returns an unusable response, DeclineDoctor falls back to deterministic diagnosis/reasoning. Backend policy remains authoritative for every action.
- **Zero Financial Execution Authority**: The LLM acts purely as an advisor. It cannot trigger gateway API calls, execute recovery, or modify incident states.
- **No Untrained ML / Deep Learning Claims**: Anomaly detection and causal diagnosis rely on rigorous statistical mechanics (two-proportion Z-tests, 95% confidence intervals, EWMA, and domain decision matrices), not unverified black-box models.

---

## 🎬 Buildathon Demo Scenarios

A fresh seed (`python scripts/seed_data.py` or clicking **Reset / Seed Demo Data** in the UI) produces three deterministic scenarios:

1. **Bank X / Card — Hero Incident**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (`processor_declined`)
   - **Confidence**: $\sim 73\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹244,773$ ($< ₹500,000$)
   - **Path**: Auto-Action Allowed ➔ `REROUTE` ➔ Outcome Measured ➔ `RESOLVED` (demonstrates automated REROUTE recovery)

2. **SBI / UPI — Ambiguous Failure**
   - **Hypothesis**: `ISSUER_SIDE_DECLINE` (diffuse decline codes)
   - **Confidence**: $\sim 69\%$ ($< 70\%$)
   - **At-Risk Revenue**: $\sim ₹171,000$
   - **Path**: Low Confidence ➔ Escalated to `ESCALATED_LOW_CONFIDENCE` ➔ Automated recovery blocked

3. **ICICI / Card — High-Value Human Approval**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (`processor_declined`)
   - **Confidence**: $\sim 71\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹667,325$ ($> ₹500,000$)
   - **Path**: High Revenue ➔ `AWAITING_HUMAN_APPROVAL` (Dual Control Required) ➔ Operator/Admin Approval ➔ `REROUTE` ➔ `RESOLVED`

---

## 🚀 Quickstart & Verification

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# (Optional) Copy environment template - runs 100% deterministically even without Gemini API key
cp .env.example .env

# Run comprehensive test suite (95 passed, 0 failed across 18 test suites)
python -m pytest

# Start FastAPI server (runs on http://localhost:8000)
python -m uvicorn app.main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install

# Run ESLint & Production Build (0 errors, 0 warnings)
npm run lint
npm run build

# Start Vite dev server (runs on http://localhost:5173)
npm run dev
```

---

## 🔬 Production Fintech Platform Capabilities

1. **Real-Time Webhook Event Ingestion (`POST /api/webhooks/payment`):** Production-style Pydantic validation, strict SHA-256 idempotency cache to prevent duplicate processing, and automatic dispatch into the 9-stage pipeline (`auto_recover=False` strictly enforced to prevent unbounded execution).
2. **Multi-Gateway Routing Optimizer:** Multi-provider profile simulation (`Provider A`, `Provider B`, `Provider C`, `Razorpay Smart Router`) scoring gateways across success probability, latency, fee cost, health state, and BIN affinity. Bounded to simulation advisory (`LIVE_CALLS_ENABLED = False`).
3. **Deep BIN-Level Intelligence:** Aggregates transaction volumes, decline rates, card schemes, decline codes, and synthetic 3DS authentication failure signals across BIN ranges. Includes an automated isolation verdict detecting whether declines are confined to a single BIN (e.g. `BIN 452114`) vs issuer-wide outages.
4. **12-Factor Structured Causal Evidence:** Upgraded diagnostic presentation exposing hypothesis, confidence, evidence FOR, evidence AGAINST, key statistical signals, provider evidence, BIN evidence, recommended action, rationale, invalidation criteria, and uncertainty bounds without leaking private reasoning tokens.
5. **Professional Counterfactual Simulator:** Side-by-side comparison of `NO INTERVENTION` baseline exposure against `REROUTE`, `ADJUST_RETRY_TIMING`, and `SUPPRESS_RETRIES` with projected success rates, lift, recovered revenue, processing fees, friction scores, and net recovery.
6. **Real-Time Incident & Alert Feed (`GET /api/incidents/feed`):** High-density streaming operations feed with severity badges, at-risk revenue, success drops, diagnosis hypotheses, and approval states.
7. **Dual-Control Human Approval Center:** Dedicated high-value approval interface supporting both `APPROVE & EXECUTE` and `REJECT` actions with strict RBAC (`ADMIN` / `OPERATOR`), immutable terminal transition (`APPROVAL_REJECTED`), and cryptographic audit logging.
8. **Closed-Loop Learning Records:** Persists recovery outcomes to `recovery_learning` table, calculating empirical historical effectiveness (e.g. 82.1% on REROUTE) to dynamically calibrate candidate confidence without bypassing policy gates.
9. **Safe Simulation A/B Experiment Framework:** Evaluates competing recovery interventions on synthetic offline cohorts (100 txns/cohort) with deterministic SHA-256 RNG seeding that remains reproducible across process restarts.
10. **Transparent Recovery Economics:** Calculates gross recovered revenue, processor costs, retry surcharges, customer friction penalties, net recovered revenue, and transparent ROI %.
11. **Customer-Level Retry Safety:** Enforces per-customer retry limits (max 2 retries), cooldowns, and friction score safety on anonymized cardholder tokens (`CUST_XXXX`) without PII exposure.
12. **Enterprise Benchmark Evaluation:** 60-scenario ground truth and 210-scenario stress benchmark formally proving **UNSAFE AUTOMATIC ACTIONS = 0** and 100% policy compliance.

---

## 🎥 Buildathon Demo

Short walkthrough of the complete Track 03 recovery loop:
payment degradation → evidence → AI diagnosis → confidence/policy gate → bounded recovery → measured revenue recovery → audit trail.

Demo video: [Add final demo/video link before submission]

### 📊 Verified Final Results

- **₹496,880.95** recovered revenue
- **52** transactions flipped
- **₹489,878.38** net recovery
- **25.98%** recovery rate
- **6995.7%** ROI
- **82.1%** learning efficacy
- **95** backend tests passed (0 failed across 18 test suites)
- **0** frontend lint errors / warnings
- **0** unsafe automatic actions in the benchmark (100% policy compliance)

---

## 🔒 Security & Safe-Execution Guarantees

- **`LIVE_CALLS_ENABLED = False` strictly enforced:** Zero financial exposure. No real money moved.
- **Strict Sandbox Modes:** All provider routing and gateway profiles execute in simulation/sandbox mode.
- **Zero Raw Secrets / Zero PII:** No cardholder names, PANs, CVVs, or live credentials stored or logged.
- **Append-Only Cryptographic Audit:** SHA-256 hash chains over every state transition and human decision.

---

## 📚 Documentation Index

- [Architecture Guide & Production Architecture](docs/ARCHITECTURE.md)
- [Product Specification & Revenue Funnel](docs/PRODUCT_SPEC.md)
- [Incident State Machine](docs/STATE_MACHINE.md)
- [Safety & Guardrails Specification](docs/SAFETY.md)
- [API Reference](docs/API.md)
- [End-to-End Demo Guide](docs/DEMO_GUIDE.md)
- [Ground-Truth Model & Safety Evaluation](docs/EVALUATION.md)
- [Security Architecture & Zero-PII Policy](docs/SECURITY.md)
