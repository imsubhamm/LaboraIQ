# LaboraIQ AWS baseline

This module establishes encrypted, private foundational services. It does not deploy
application images or expose ingress. Copy an environment example outside source
control, review every value, then run `terraform init`, `terraform plan -var-file=...`,
and an approved `terraform apply`.

Production requires review of multi-AZ RDS sizing, VPC egress/endpoints, WAF and load
balancer ingress, DNS/TLS, ECS task IAM, alarm notification targets, backup restore
testing, CloudTrail, Security Hub, and organization-level guardrails. Secrets are
created as containers only; values must be populated through an approved secrets
workflow.

