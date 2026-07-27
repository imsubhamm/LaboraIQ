# Core platform security baseline

- Secrets and credentials are excluded from source; runtime values come from validated
  environment variables and AWS Secrets Manager.
- Production development-auth bypass is forbidden. OIDC validation must pin issuer,
  audience and signing algorithm, and enforce expiry.
- API authorization and tenant/branch scope are authoritative. ORM parameterization
  prevents string-built SQL injection.
- CORS uses an allowlist; response security headers and a 1 MiB request limit are set.
  A gateway/WAF supplies rate limiting before production.
- Logs use correlation IDs and must exclude authorization headers, passwords, tokens,
  refresh tokens and secrets. Audit JSON applies sensitive-key masking.
- RDS, S3, SQS, logs and secrets use KMS encryption. IAM task roles must grant only
  named resource actions; no wildcard data-plane permissions.
- CI runs dependency review, secret scanning, static checks, tests and builds. Alerts,
  patching, backup restore, incident response and access review require operational
  procedures before release.

