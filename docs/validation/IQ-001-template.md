# IQ-001 — Installation qualification template

Record environment, executor, date, approved change/commit, artifact digests and
deviations. Verify: repository tag; dependency lockfiles; secret-scan result; runtime
versions; migration level; PostgreSQL/RDS configuration; KMS encryption; S3 public
access blocks/versioning; SQS/DLQ encryption; Secrets Manager references; CloudWatch
retention/alarms; container health; backup policy; time synchronization.

Each step requires expected result, observed evidence link, pass/fail, executor and
reviewer signatures. Installation qualification does not establish clinical fitness.

