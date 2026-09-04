# DeclineDoctor Security Architecture 🔒

DeclineDoctor treats security, tamper-resistance, and authorization as foundational platform guarantees.

---

## 1. Secret Protection & Zero-Credential Exposure

1. **No Hardcoded Credentials:** No API keys, database passwords, or payment gateway secrets are stored in version control.
2. **Environment File Isolation:** `.env`, `.env.local`, `*.env`, and database files `*.db` are strictly excluded in `.gitignore`.
3. **Graceful Degradation Without Live Keys:** The system defaults to deterministic sandbox operation if `GEMINI_API_KEY` or payment provider credentials are unset. Live keys are never required to run local tests or buildathon demonstrations.

---

## 2. Cryptographic Append-Only Audit Trail

Audit logs are cryptographically sealed using SHA-256 parent hash chaining:

$$H_i = \text{SHA-256}(H_{i-1} \parallel \text{Timestamp} \parallel \text{Actor} \parallel \text{EventType} \parallel \text{DetailsJSON})$$

- **Tamper Detection:** Modifying any record's timestamp, event type, actor, or details invalidates the current record hash and breaks all subsequent links in the chain.
- **Independent Verification:** The endpoint `GET /api/incidents/{id}/audit/verify` traverses the entire record sequence, independently recomputes hashes, and reports any tampering with record IDs.

---

## 3. Role-Based Access Control (RBAC)

DeclineDoctor restricts critical operational levers based on authenticated roles:

| Role | Permitted Actions | Restricted Actions |
| :--- | :--- | :--- |
| **ADMIN** | Full platform control, approvals, rollbacks, data reset | None |
| **OPERATOR** | Recovery approvals, manual rollbacks, simulation | Infrastructure re-configuration |
| **ANALYST** | View analytics, segment explorer, evaluation metrics | Financial approvals, recovery execution, rollbacks |
| **VIEWER** | Read-only observation of incidents and audit logs | All state-modifying actions |

Roles are enforced at the API boundary in `backend/app/policy.py` using `can_approve_recovery(role)`.

---

## 4. Input Validation & Strict Schema Boundaries

- **Extra Field Forbiddance:** The recovery contract `RecoveryRequest` strictly enforces `extra="forbid"`, rejecting unknown parameters, injection attempts, and unexpected flags with HTTP 422.
- **Allowed Action Enums:** Recommended actions are restricted to `Literal["REROUTE", "ADJUST_RETRY_TIMING", "SUPPRESS_RETRIES"]`.
- **Numeric Grounding Validation:** LLM output is parsed against evidence numbers. Any hallucinated statistics or unverified financial figures are caught and rejected prior to persistence.
