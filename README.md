# DeclineDoctor 🩺💳

**Autonomous Payment Decline Diagnosis, Safe Intervention & Revenue Recovery Agent**

DeclineDoctor continuously monitors payment transaction streams, detects anomalous failure spikes across card and payment method segments, conducts deterministic root-cause diagnosis backed by numeric-grounded LLM narrative synthesis, enforces strict financial guardrails and human-in-the-loop approvals, executes safe recovery simulations, and records tamper-proof audit trails.

---

## 🎯 Core Intended Flow

```
DETECT ➔ EVIDENCE ➔ DIAGNOSE ➔ CONFIDENCE GATE ➔ ACTION DECISION ➔ HUMAN APPROVAL GATE ➔ RECOVERY SIMULATION ➔ RE-MEASURE ➔ RECOVERED REVENUE ➔ TERMINAL STATE ➔ AUDIT TRAIL
```

1. **DETECT**: Time-window anomaly detection computes drops in success rates against a 14-day rolling baseline for each issuer/payment-method segment.
2. **EVIDENCE**: Collects failure concentration ratios, sample sizes, and dominant decline codes from actual transaction logs.
3. **DIAGNOSE**: Deterministic rule engine calculates confidence using:
   $$\text{Confidence} = 0.5 \times \text{Concentration} + 0.3 \times \text{Dominant Share} + 0.2 \times \min\left(\frac{\text{Sample Size}}{150}, 1.0\right)$$
4. **CONFIDENCE GATE**: Confidence $\ge 0.70$ is required for automated recovery proposals. If confidence $< 0.70$, the incident is immediately marked `ESCALATED_LOW_CONFIDENCE` with an `ESCALATION` audit log and zero automated actions.
5. **ACTION DECISION**: Actions are mapped to root causes (`REROUTE`, `ADJUST_RETRY_TIMING`, `SUPPRESS_RETRIES`). Advisory LLM summaries are generated using Gemini (`gemini-2.5-flash`) with strict numeric grounding verification to prevent hallucinations.
6. **HUMAN APPROVAL GATE**: If at-risk revenue $> ₹500,000$, automatic execution is strictly blocked. The incident enters `AWAITING_HUMAN_APPROVAL`, and recovery requires explicit human confirmation.
7. **RECOVERY SIMULATION**: Safely tests the recovery action against failed transactions (strictly capped at $\le 2$ retries per transaction) and checks for minimum measurable improvement ($\ge 5$ percentage points).
8. **RE-MEASURE & REVENUE**: Calculates actual recovered revenue from recovered transactions.
9. **TERMINAL STATE PROTECTION**: Once an incident reaches a terminal state (`RESOLVED`, `ESCALATED_LOW_CONFIDENCE`, `ESCALATED_INSUFFICIENT_RECOVERY`, `ESCALATED_LOW_REVENUE`), it cannot be re-diagnosed, reopened, or re-recovered.
10. **AUDIT TRAIL**: Every lifecycle change and security decision is persisted to the backend database (`AuditLog` table) and rendered chronologically in the audit trail.

---

## 🛡️ Non-Negotiable Safety Guardrails

| Guardrail | Threshold / Policy | Backend Enforcement |
|---|---|---|
| **Confidence Gate** | $\ge 0.70$ (70%) | Incidents $< 0.70$ transition to `ESCALATED_LOW_CONFIDENCE` |
| **Minimum Revenue for Action** | $\ge ₹50,000$ | Incidents $< ₹50,000$ escalate to `ESCALATED_LOW_REVENUE` |
| **Human Approval Cap** | $> ₹500,000$ | Automatically holds in `AWAITING_HUMAN_APPROVAL` |
| **Retry Budget Cap** | $\le 2$ retries/txn | Hard ceiling enforced in recovery simulation |
| **Measurable Threshold** | $\ge 5$ pp improvement | Below 5 pp escalates to `ESCALATED_INSUFFICIENT_RECOVERY` |
| **Terminal State Invariance** | Immutable | Terminal incidents reject repeated diagnosis or actions |
| **LLM Advisory Boundary** | Advisory only | Backend validates all actions against strict schema and limits |

---

## 🎬 Buildathon Demo Scenarios

A fresh seed (`python scripts/seed_data.py` or clicking **Reset / Seed Demo Data** in the UI) produces three deterministic scenarios:

1. **Bank X / Card (Hero Incident)**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (processor_declined)
   - **Confidence**: $\sim 73\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹244,000$ ($< ₹500,000$)
   - **Path**: Auto-Action Allowed ➔ `REROUTE` ➔ Outcome Measured ➔ `RESOLVED` ($\sim ₹107,000$ recovered)

2. **SBI / UPI (Ambiguous Failure)**
   - **Hypothesis**: `ISSUER_SIDE_DECLINE` (diffuse decline codes)
   - **Confidence**: $\sim 69\%$ ($< 70\%$)
   - **At-Risk Revenue**: $\sim ₹171,000$
   - **Path**: Low Confidence ➔ Escalated to `ESCALATED_LOW_CONFIDENCE` ➔ Zero automated recovery attempted

3. **ICICI / Card (High-Value Human Approval)**
   - **Hypothesis**: `ROUTING_CONNECTIVITY_ISSUE` (processor_declined)
   - **Confidence**: $\sim 71\%$ ($\ge 70\%$)
   - **At-Risk Revenue**: $\sim ₹667,000$ ($> ₹500,000$)
   - **Path**: High Revenue ➔ `AWAITING_HUMAN_APPROVAL` ➔ Execution blocked without human review ➔ One-click human approval ➔ `REROUTE` ➔ `RESOLVED` ($\sim ₹272,000$ recovered)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Backend Setup

```bash
cd backend

# Create virtual environment (optional)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and insert your Gemini API Key:
# GEMINI_API_KEY=your_key_here

# Seed initial database
python scripts/seed_data.py

# Run FastAPI backend
uvicorn app.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run Vite dev server
npm run dev
```

The frontend dashboard will be live at `http://localhost:5173`.

---

## 🧪 Verification & Testing

Run all backend unit and integration tests (24 automated tests):
```bash
cd backend
python -m pytest
```

Run frontend linting and build validation:
```bash
cd frontend
npm run lint
npm run build
```

---

## 📁 Repository Structure

```
declinedoctor/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   │   ├── dashboard.py     # Active incident metrics, global rate, revenue at risk
│   │   │   ├── incidents.py     # Incident detail, diagnosis, recovery, audit trail
│   │   │   └── simulate.py      # Seed and anomaly detection trigger
│   │   ├── database.py          # SQLAlchemy SQLite connection
│   │   ├── detection.py         # 14-day rolling baseline anomaly detection
│   │   ├── diagnosis.py         # Confidence formula and terminal protection
│   │   ├── llm_narrator.py      # Gemini structured output & numeric grounding
│   │   ├── main.py              # FastAPI application setup & CORS
│   │   ├── models.py            # SQLite schema (Transactions, Incidents, AuditLog)
│   │   └── recovery_agent.py    # Guardrail checks, simulation & recovery outcomes
│   ├── scripts/
│   │   └── seed_data.py         # Deterministic seed generator for 3 demo scenarios
│   └── tests/
│       ├── test_diagnosis.py            # Confidence formula & terminal state tests
│       ├── test_human_approval_flow.py  # End-to-end human approval guardrail test
│       ├── test_llm_safety.py           # Numeric grounding & hallucination tests
│       ├── test_recovery_api_contract.py# API validation contract tests
│       ├── test_recovery_block_response.py # Blocked response schema tests
│       └── test_recovery_guardrails.py  # Financial limits, retry caps, terminal guards
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # Metrics cards, active/resolved tabs, demo reset
│   │   │   ├── IncidentView.jsx # Live detail, action cards, human approval flow
│   │   │   └── AuditTrail.jsx   # Real persisted backend audit log timeline
│   │   ├── api.js               # Axios client configured for backend proxy
│   │   ├── App.jsx              # Main routing and navigation
│   │   └── main.jsx
│   └── package.json
└── docs/
    ├── ARCHITECTURE.md          # Detailed architectural specification
    └── PRODUCT_SPEC.md          # Complete product and functional requirements
```
