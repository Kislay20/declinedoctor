# DeclineDoctor 🩺💳

**Autonomous Payment Decline Diagnosis, Safe Intervention & Revenue Recovery Platform**

DeclineDoctor continuously monitors payment transaction streams, detects anomalous failure spikes across card and payment method segments, conducts deterministic root-cause diagnosis backed by numeric-grounded LLM narrative synthesis, enforces strict financial guardrails and human-in-the-loop approvals, executes safe recovery simulations, and records append-only, SHA-256 tamper-proof audit trails.

---

## 🎯 Core Intended Lifecycle

```
DETECT ➔ EVIDENCE ➔ DIAGNOSE ➔ CONFIDENCE GATE ➔ ACTION DECISION ➔ HUMAN APPROVAL GATE ➔ RECOVERY SIMULATION ➔ RE-MEASURE ➔ RECOVERED REVENUE ➔ TERMINAL STATE ➔ AUDIT PROOF
```

1. **DETECT**: Statistical anomaly detection evaluates success rate drops against 14-day rolling baselines using pooled two-proportion Z-tests, p-values, 95% confidence intervals, and hourly EWMA.
2. **EVIDENCE**: Collects failure concentration ratios, transaction volume, and dominant decline codes from actual logs.
3. **DIAGNOSE**: Deterministic causal classification maps decline codes to hypotheses and calculates confidence:
   $$\text{Confidence} = 0.5 \times \text{Concentration} + 0.3 \times \text{Dominant Share} + 0.2 \times \min\left(\frac{\text{Sample Size}}{150}, 1.0\right)$$
4. **CONFIDENCE GATE**: Confidence $\ge 0.70$ is mandatory. If confidence $< 0.70$, the incident transitions immediately to `ESCALATED_LOW_CONFIDENCE` with an `ESCALATION` audit log and automated action is blocked.
5. **ACTION DECISION**: Evaluates counterfactual outcomes across `REROUTE`, `ADJUST_RETRY_TIMING`, and `SUPPRESS_RETRIES`. Advisory LLM summaries are generated via the official `google.genai` SDK with strict numeric grounding verification.
6. **HUMAN APPROVAL GATE**: If at-risk revenue exceeds ₹500,000, automated execution is blocked. The incident enters `AWAITING_HUMAN_APPROVAL`, requiring authorization from an `ADMIN` or `OPERATOR` role.
7. **RECOVERY SIMULATION**: Safely tests the recovery action against failed transactions (strictly capped at $\le 2$ retries per transaction) and verifies minimum measurable improvement ($\ge 5.0$ percentage points).
8. **RE-MEASURE & REVENUE**: Calculates actual recovered revenue from recovered transactions.
9. **TERMINAL STATE PROTECTION**: Terminal states (`RESOLVED`, `ESCALATED_LOW_CONFIDENCE`, `ESCALATED_INSUFFICIENT_RECOVERY`, `ESCALATED_LOW_REVENUE`, `ROLLED_BACK`) are strictly immutable.
10. **CRYPTOGRAPHIC AUDIT PROOF**: Every lifecycle change is permanently recorded in a SHA-256 parent-hash chained audit log, independently verifiable for tamper detection.

---

## 🛡️ Non-Negotiable Safety Guardrails

| Guardrail | Threshold / Policy | Backend Enforcement |
|---|---|---|
| **Confidence Gate** | $\ge 0.70$ (70%) | Incidents $< 0.70$ transition to `ESCALATED_LOW_CONFIDENCE` |
| **Minimum Revenue for Action** | $\ge ₹50,000$ | Incidents $< ₹50,000$ escalate to `ESCALATED_LOW_REVENUE` |
| **Human Approval Cap** | $> ₹500,000$ | Automatically holds in `AWAITING_HUMAN_APPROVAL` |
| **Retry Budget Cap** | $\le 2$ retries/txn | Hard ceiling enforced in recovery simulation |
| **Measurable Threshold** | $\ge 5.0$ pp improvement | Below 5 pp escalates to `ESCALATED_INSUFFICIENT_RECOVERY` |
| **Terminal State Invariance** | Immutable | Terminal incidents reject repeated diagnosis or actions |
| **Role-Aware Access Control** | ADMIN / OPERATOR | Unauthorized roles (`VIEWER`, `ANALYST`) blocked from financial actions |
| **LLM Advisory Boundary** | Advisory only | Backend validates all actions against strict schema and limits |

---

## 🎬 Buildathon Demo Scenarios

A fresh seed (`python scripts/seed_data.py` or clicking **Reset / Seed Demo Data** in the UI) produces three deterministic scenarios:

1. **Bank X / Card (Hero Incident)**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (`processor_declined`)
   - **Confidence**: $\sim 73\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹244,773$ ($< ₹500,000$)
   - **Path**: Auto-Action Allowed ➔ `REROUTE` ➔ Outcome Measured ➔ `RESOLVED` ($\sim ₹107,791$ recovered)

2. **SBI / UPI (Ambiguous Failure)**
   - **Hypothesis**: `ISSUER_SIDE_DECLINE` (diffuse decline codes)
   - **Confidence**: $\sim 69\%$ ($< 70\%$)
   - **At-Risk Revenue**: $\sim ₹171,000$
   - **Path**: Low Confidence ➔ Escalated to `ESCALATED_LOW_CONFIDENCE` ➔ Automated recovery blocked

3. **ICICI / Card (High-Value Human Approval)**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (`processor_declined`)
   - **Confidence**: $\sim 71\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹667,325$ ($> ₹500,000$)
   - **Path**: High Revenue ➔ `AWAITING_HUMAN_APPROVAL` ➔ Operator/Admin Approval ➔ `REROUTE` ➔ `RESOLVED` ($\sim ₹272,925$ recovered)

---

## 🚀 Quickstart & Verification

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run pytest (47 comprehensive tests)
python -m pytest

# Start FastAPI server
python -m uvicorn app.main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install

# Run ESLint & Production Build
npm run lint
npm run build

# Start Vite dev server
npm run dev
```

---

## 📚 Documentation Index

- [Architecture Guide](docs/ARCHITECTURE.md)
- [Product Specification](docs/PRODUCT_SPEC.md)
- [Incident State Machine](docs/STATE_MACHINE.md)
- [Safety & Guardrails](docs/SAFETY.md)
- [API Reference](docs/API.md)
- [End-to-End Demo Guide](docs/DEMO_GUIDE.md)
- [Ground-Truth Model Evaluation](docs/EVALUATION.md)
- [Security Architecture](docs/SECURITY.md)
