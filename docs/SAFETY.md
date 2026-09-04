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

## 2. Action / Hypothesis Compatibility Matrix

Actions must conform strictly to domain causality:

| Diagnostic Hypothesis | Permitted Action | Prohibited Actions | Rationale |
| :--- | :--- | :--- | :--- |
| `ROUTING_CONNECTIVITY_ISSUE` | `REROUTE` | `ADJUST_RETRY_TIMING`, `SUPPRESS_RETRIES` | Switches failing gateway provider to an alternate healthy partner. |
| `BIN_LEVEL_TEMPORARY_ISSUE` | `ADJUST_RETRY_TIMING` | `REROUTE`, `SUPPRESS_RETRIES` | Applies jittered backoff for rate/velocity throttles on card BINs. |
| `ISSUER_SIDE_DECLINE` | `SUPPRESS_RETRIES` | `REROUTE`, `ADJUST_RETRY_TIMING` | Halts immediate retries to prevent customer account lockouts and fee churn. |
| `INSUFFICIENT_SIGNAL` | `SUPPRESS_RETRIES` | `REROUTE`, `ADJUST_RETRY_TIMING` | Diffuse, ambiguous failure codes are not eligible for automated routing changes. |

Any request attempting an incompatible action is rejected with `HTTP 422 Unprocessable Content`.

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
