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

---

## 5. Explicit Disablement of Live Money Transactions

- **Zero Live Execution Risk:** The prototype is configured with `is_live_allowed: False`. Under no circumstances can live money transfers, live card debits, or active production merchant account funds be moved by DeclineDoctor.
- **Provider Sandbox Guard:** Even if live Razorpay credentials are inadvertently supplied, the provider abstraction layer intercepts execution and locks routing probes to test sandbox mode with `"LIVE STRICTLY DISABLED"`.

---

## 6. Customer Privacy & Zero-PII Guarantee

- **Anonymized Customer Identifiers:** Cardholders are represented exclusively via synthetic pseudo-anonymous tokens (`CUST_1042`, `CUST_2081`).
- **No Sensitive Financial Data:** No Primary Account Numbers (PAN), CVVs, cardholder names, billing addresses, or phone numbers are ingested, stored, or processed by DeclineDoctor.
