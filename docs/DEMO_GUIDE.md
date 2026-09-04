# DeclineDoctor End-to-End Demo Guide 🚀

This guide provides a deterministic, step-by-step walkthrough of the DeclineDoctor buildathon demonstration flows and product features.

---

## Prerequisites

Start the application services:

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 1. Fresh Baseline Setup

Click **"Reset / Seed Demo Data"** at the top right of the Dashboard.
This seeds 2,610 synthetic transactions across baseline and incident windows and triggers anomaly detection.

**Expected Initial State:**
- Active Incidents: **3**
- Active Revenue at Risk: **₹1,083,877.91**
- Global Success Rate: **~63.5%**
- Total Recovered Revenue: **₹0.00**

---

## 2. Scenario 1: Bank X (High-Confidence Autonomous Recovery)

1. Click on the **Bank X card** incident card on the Dashboard.
2. Observe the evidence:
   - Baseline success rate: ~95%
   - Incident success rate: ~56% (-38.7 pp drop)
   - Dominant decline code: `processor_declined` (~86% share)
3. Click **"Run AI Diagnosis"**:
   - Identified Hypothesis: `ROUTING_CONNECTIVITY_ISSUE`
   - Diagnostic Confidence: **0.73** (Safe: &ge; 0.70)
   - Safety Gate Banner: **SAFE TO EXECUTE**
   - Counterfactual Matrix recommends: `REROUTE` (+18.3 pp projected lift)
4. Click **"Execute Automated Recovery: REROUTE"**:
   - Status transitions to: **RESOLVED**
   - Measured Lift: **+18.3 pp**
   - Recovered Revenue: **₹107,791.84**
5. Click **"Cryptographic Audit Trail"**:
   - Observe append-only events: `ANOMALY_DETECTED` &rarr; `DIAGNOSED` &rarr; `ACTION_SELECTED` &rarr; `ACTION_APPLIED` &rarr; `OUTCOME_MEASURED`
   - Notice the green badge: **SHA-256 HASH CHAIN: VERIFIED TAMPER-FREE**

---

## 3. Scenario 2: SBI (Low-Confidence Safety Escalation)

1. Return to Dashboard and select the **SBI upi** incident.
2. Observe the evidence:
   - Diffuse decline distribution (`insufficient_funds`, `unknown_error`)
3. Click **"Run AI Diagnosis"**:
   - Confidence: **0.69** (< 0.70 threshold)
   - Safety Gate Banner: **AUTOMATED RECOVERY BLOCKED**
   - State transitions immediately to: **ESCALATED_LOW_CONFIDENCE**
4. Automated recovery button is suppressed.
5. In **"Evidence-Grounded Explainability"**, expand the accordion:
   - *"Why did DeclineDoctor not act?"*: Explains that confidence 0.69 is below the mandatory 0.70 safety threshold, avoiding misrouting legitimate customer transactions.

---

## 4. Scenario 3: ICICI (High-Value Human Approval Dual Control)

1. Return to Dashboard and select the **ICICI card** incident.
2. Observe the evidence:
   - Revenue at risk: **₹667,325.06** (Exceeds ₹500,000 auto-approval ceiling)
3. Click **"Run AI Diagnosis"**:
   - Identified Hypothesis: `ROUTING_CONNECTIVITY_ISSUE`
   - Confidence: **0.71** (&ge; 0.70)
   - Safety Gate Banner: **HUMAN APPROVAL REQUIRED**
   - State: **AWAITING_HUMAN_APPROVAL**
4. Notice the Recovery Button:
   - *"Grant Human Approval & Execute REROUTE (OPERATOR)"*
5. Return to Dashboard and switch to the **"Approval Queue"** tab:
   - Notice the ICICI incident is listed with severity `CRITICAL`
   - Switch role in navbar to `VIEWER`: approval button is disabled (role not authorized)
   - Switch role back to `OPERATOR` or `ADMIN`: click **"Approve Recovery"**
6. Recovery executes:
   - Status transitions to: **RESOLVED**
   - Recovered Revenue: **₹272,925.82**
   - Total Recovered Revenue on Dashboard reaches: **₹380,717.66**
   - Revenue Recovery Rate reaches: **54.14%**!

---

## 5. Rollback Verification

1. Open the resolved ICICI incident.
2. Click **"Rollback Recovery"** at the top right.
3. Enter confirmation reason: *"Circuit breaker tripped on downstream route"*.
4. System reverts the 40 flipped transactions, updates state to **ROLLED_BACK**, and logs `ROLLBACK_EXECUTED` in the cryptographic audit trail.

---

---

## 6. Model Evaluation Benchmark, Deep BIN Intelligence & Simulation Lab

1. Navigate to **"Model Evaluation"** in the top navbar:
   - View genuine benchmark calculated over 60 ground-truth scenarios.
   - Toggle **"Enterprise Stress & Safety Suite (210 Cases)"**:
     * Verified **UNSAFE AUTOMATIC ACTIONS = 0**
     * 100% adherence on `DO NOT ACT` scenarios
     * 100% human-approval gate enforcement on high-value scenarios.
2. Navigate to **"Segment Explorer"**:
   - Explore **"Issuer & Rail Segments"** with volume, decline codes, and failure distributions.
   - Switch to **"Deep BIN Intelligence"** tab:
     * Inspect card range telemetry across monitored BINs (e.g. `452114`, `524188`, `411111`).
     * Observe the **Causal Isolation Verdict**: *"Evidence indicates the incident is isolated to BIN 452114 rather than an issuer-wide decline pattern."*
     * Review synthetic 3DS authentication failure signals and gateway dispersions.
3. Navigate to **"Simulation Lab"**:
   - **Policy Simulator:** Test policy gates across custom volumes, failure rates, ticket sizes, and confidence levels.
   - **Event Stream & Webhook Ingestion Probe:** Test single event injection or trigger `POST /api/webhooks/payment` to verify Pydantic validation, idempotency caching, and the 9-stage pipeline trace (`auto_recover=False` guaranteed).
   - **Recovery Strategy Experiments:** Run offline A/B cohort experiments (100 txns/cohort) with deterministic SHA-256 seeding and two-proportion z-tests.
   - **Customer Safety:** Inspect per-cardholder retry limits (max 2 retries), 15-minute cooldowns, and friction indices (`CUST_1042`, etc.).
   - **Provider Routing Optimizer:** Run multi-gateway scoring probes to evaluate composite scores for `Provider A`, `Provider B`, `Provider C`, and `Razorpay Smart Router`.
4. Inspect Dashboard Command Center Panels:
   - **Multi-Gateway Routing Intelligence:** View top-ranked gateway route, health, latency, fee costs, and recommendation banner.
   - **Real-Time Incident Feed:** Switch to "Activity Feed" tab to see chronological streaming anomalies.
   - **Dual-Control Approval Queue:** Inspect held incidents exceeding ₹500,000 ceiling.
   - **Closed-Loop Learning:** View historical effectiveness (e.g. 82% on REROUTE across 38+ attempts) and prior calibration telemetry.

