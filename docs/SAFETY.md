# DeclineDoctor Safety & Guardrails Specification 🛡️

DeclineDoctor treats safety, financial limits, and operational predictability as non-negotiable backend invariants.
The LLM is strictly advisory. All authorization decisions are owned by backend services.

---

## 1. Core Financial & Safety Boundaries

| Safety Guardrail | Threshold / Limit | Failure State | Enforced At |
| :--- | :--- | :--- | :--- |
| **Confidence Gate** | &ge; 0.70 (70%) | `ESCALATED_LOW_CONFIDENCE` | `app/recovery_agent.py` & `app/policy.py` |
| **Revenue Floor Gate** | &ge; ₹50,000.00 | `ESCALATED_LOW_REVENUE` | `app/recovery_agent.py` & `app/policy.py` |
| **Auto-Approval Ceiling**| &le; ₹500,000.00 | `AWAITING_HUMAN_APPROVAL` | `app/recovery_agent.py` & `app/policy.py` |
| **Retry Budget Cap** | Max 2 retries per txn | Excluded from recovery pool | `app/recovery_agent.py` & `app/simulation.py` |
| **Efficacy Threshold** | &ge; 5.0 pp lift | `ESCALATED_INSUFFICIENT_RECOVERY` | `app/recovery_agent.py` |
| **Terminal Immutability**| Terminal states locked | `RECOVERY_BLOCKED` | `app/policy.py` |

---

## 2. Expanded Action / Hypothesis Compatibility Matrix

Actions must conform strictly to domain causality:

| Diagnostic Hypothesis | Permitted Actions | Prohibited Actions | Rationale |
| :--- | :--- | :--- | :--- |
| `ROUTING_CONNECTIVITY_ISSUE` | `REROUTE`, `PROVIDER_WEIGHT_ADJUSTMENT`, `INTELLIGENT_RETRY` | `SUPPRESS_RETRIES` | Switches failing gateway or reallocates gateway traffic weights away from degraded processor. |
| `BIN_LEVEL_TEMPORARY_ISSUE` | `ADJUST_RETRY_TIMING`, `INTELLIGENT_RETRY`, `PAYMENT_METHOD_FALLBACK` | `REROUTE`, `SUPPRESS_RETRIES` | Applies jittered backoff or prompts customer to switch payment method during BIN throttle. |
| `ISSUER_SIDE_DECLINE` | `SUPPRESS_RETRIES`, `PAYMENT_METHOD_FALLBACK` | `REROUTE`, `PROVIDER_WEIGHT_ADJUSTMENT` | Prevents repeated issuer charges; prompts alternate instrument if card limits hit. |
| `INSUFFICIENT_SIGNAL` | `SUPPRESS_RETRIES` (Safe hold) | `REROUTE`, `ADJUST_RETRY_TIMING`, `PROVIDER_WEIGHT_ADJUSTMENT` | Ambiguous noise is never routed automatically without statistical significance. |

Any request attempting an incompatible action is rejected with `HTTP 422 Unprocessable Content`.

---

## 2.1 Customer-Level Retry Safety & Friction Scoring (`app/customer_safety.py`)

To protect end-cardholders from fatigue, bank account lockouts, and unnecessary fraud alerts:
- **Anonymized Identifiers:** Cardholders are tracked via anonymized tokens (`CUST_1042`, `CUST_2081`) without storing PII.
- **Hard Per-Customer Cap:** Maximum 2 recovery retries per customer across all active incident windows.
- **Enforced Cooldowns:** Minimum 15-minute cooldown between automated retry attempts on identical payment credentials.
- **Friction Index:** Calculates customer friction risk (0-100). When friction exceeds 60, automated retries are suppressed and the system surfaces an organic checkout fallback.

---

## 2.2 Closed-Loop Learning Non-Bypass Invariant

DeclineDoctor incorporates a closed-loop outcome feedback loop (`app/learning.py`), with strict architectural separation:
- **What Learning Can Modify:** Recommendation ranking, expected percentage lift, and diagnostic confidence modifiers ($\pm 0.05$).
- **What Learning CANNOT Modify:** Revenue floors (₹50k), auto-approval ceilings (₹500k), role authorizations (ADMIN/OPERATOR only), retry caps ($\le 2$), or terminal state immutability.
- **Safety Invariant:** A recovery action can never be automatically executed solely because historical learning was favorable if any policy gate fails.

---

## 3. Role-Based Access Control (RBAC)

DeclineDoctor enforces role authorization on high-value approvals and operational rollbacks:

| Role | Permissions | High-Value Approval (> ₹500k) | Rollback Execution | View Dashboards |
| :--- | :--- | :---: | :---: | :---: |
| **ADMIN** | Full administrative rights | ✅ YES | ✅ YES | ✅ YES |
| **OPERATOR** | Incident response & approval | ✅ YES | ✅ YES | ✅ YES |
| **ANALYST** | Read-only analysis & metrics | ❌ NO | ❌ NO | ✅ YES |
| **VIEWER** | Read-only observation | ❌ NO | ❌ NO | ✅ YES |

If an unauthorized role (`VIEWER` or `ANALYST`) attempts to approve an incident or trigger a rollback:
- The request is blocked with `HTTP 200 / 400` indicating `unauthorized_role`.
- A `RECOVERY_BLOCKED` event is logged in the append-only cryptographic audit trail.

---

## 4. LLM Trust Boundary & Numeric Grounding

The AI narrative engine is isolated by strict trust boundaries:

1. **Structured Output Schema:** Pydantic `ActionProposal` enforces schema contracts (`narrative`, `recommended_action`, `reasoning`).
2. **Action Compatibility:** The proposed action must match the deterministic domain action for the diagnosed hypothesis.
3. **Numeric Grounding Validation:** The narrative is stripped of timestamps, ISO dates, clock times, durations (e.g. `24-hour`), identifiers, and list numbers. Every remaining numeric token must exist within the evidence payload (percentages, transaction counts, drop values). Unsubstantiated numeric claims trigger immediate rejection.
4. **Deterministic Fallback:** If the LLM call fails, times out, or violates validation, DeclineDoctor falls back seamlessly to deterministic rule-based explanations without interrupting operations.
