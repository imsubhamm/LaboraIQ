# RISK-001 — Core platform risk assessment

Status: Controlled draft · Method: Severity (S), Probability (P), Detectability (D)
scored 1–5; RPN = S × P × D. Scores are preliminary and require Quality approval.

| Risk | Cause / effect | Initial S/P/D (RPN) | Controls | Residual S/P/D (RPN) |
|---|---|---:|---|---:|
| Cross-tenant data exposure | unscoped query exposes another laboratory | 5/3/4 (60) | authenticated context, service/query scope, isolation tests, denied-access audit | 5/1/2 (10) |
| Unauthorized approval authority | over-broad role later permits clinical approval | 5/3/3 (45) | granular configurable permissions, least privilege, explicit future clinical permissions | 5/1/2 (10) |
| Missing audit record | mutation and evidence are not atomic | 5/3/4 (60) | same transaction, required service path, OQ reconciliation | 5/1/2 (10) |
| Incorrect branch context | action applied to unintended laboratory | 5/3/3 (45) | identity-derived branch scope, visible context, branch tests | 5/1/2 (10) |
| Database data loss | failure or erroneous operation | 5/2/4 (40) | encrypted backups, retention, deletion protection, restore qualification | 5/1/2 (10) |
| Secrets exposure | secret committed or logged | 4/3/3 (36) | environment validation, secret scanning, Secrets Manager, masking | 4/1/2 (8) |
| Untraceable configuration change | evidence mutable or missing correlation | 4/3/4 (48) | append-only event, DB trigger, correlation ID, S3 evidence roadmap | 4/1/2 (8) |

Residual acceptance and additional mitigations require Quality and system-owner
approval before production use.

