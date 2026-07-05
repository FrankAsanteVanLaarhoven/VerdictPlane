# EAG-Bench — Regulatory & Threat Coverage

> **Scope — coverage, not certification.** This is an evidence map: which benchmark cases exercise each control or threat, compiled from the corpus's `compliance_mappings` and `attack_annotations`. It does **not** claim VerdictPlane satisfies any regulation or is certified against any standard; it shows where the benchmark provides testable evidence.

Compiled by `make compliance-report` from **115** cases (single-action corpus + red-team track).

## Regulatory coverage

### EU AI Act

| control | cases | count |
| --- | --- | --- |
| **Art.10** | `data_export_pii.export_https.deny`, `data_export_pii.export_internal_nonpii.require_human`, `data_export_pii.export_pii.allow_after_approval`, `data_export_pii.export_pii.deny_after_timeout`, `data_export_pii.export_pii_internal.require_human`, `data_export_pii.export_to_external.deny` … | 19 |
| **Art.14** | `cloud_iam.create_key.allow_after_approval`, `cloud_iam.create_user.require_human`, `cloud_iam.delete_role.require_human`, `code_deployment.deploy_prod.allow_after_approval`, `code_deployment.deploy_prod.deny_after_timeout`, `code_deployment.deploy_prod.deny_after_veto` … | 39 |
| **Art.15** | `model_promotion.promote_failing_gate.deny` | 1 |

### NIST AI RMF

| control | cases | count |
| --- | --- | --- |
| **GOVERN-1.1** | `cloud_iam.create_key.allow_after_approval`, `cloud_iam.create_user.require_human`, `cloud_iam.delete_role.require_human`, `code_deployment.deploy_prod.allow_after_approval`, `code_deployment.deploy_prod.deny_after_timeout`, `code_deployment.deploy_prod.deny_after_veto` … | 39 |
| **MANAGE-2.2** | `cloud_iam.attach_admin_policy.deny`, `cloud_iam.disable_mfa.deny`, `cloud_iam.rotate_access_key.allow_after_approval`, `code_deployment.deploy_unsigned_staging.deny`, `data_export_pii.export_https.deny`, `data_export_pii.export_webhook.deny` … | 14 |
| **MAP-4.1** | `code_deployment.deploy_unsigned.deny` | 1 |

### ISO/IEC 42001

| control | cases | count |
| --- | --- | --- |
| **A.12.1** | `incident_rollback.execute_during_freeze.deny_after_timeout`, `incident_rollback.propose_rollback.require_human` | 2 |
| **A.8.2** | `robotics_ot.actuate_over_limit.deny` | 1 |
| **A.9.2** | `cloud_iam.attach_admin_policy.deny`, `cloud_iam.create_scoped_role.allow`, `cloud_iam.disable_mfa.deny`, `code_deployment.deploy_unsigned_staging.deny`, `data_export_pii.export_https.deny`, `data_export_pii.export_webhook.deny` … | 16 |

## Threat coverage (attack annotations)

### OWASP LLM Top 10

| control | cases | count |
| --- | --- | --- |
| **LLM01** | `inj.exfil_pii`, `mcp_write_tool.delete_traversal.deny`, `mcp_write_tool.path_traversal.deny`, `tc.traverse_after_list` | 4 |
| **LLM06** | `data_export_pii.export_https.deny`, `data_export_pii.export_to_external.deny`, `data_export_pii.export_webhook.deny`, `hr_employee_data.bulk_export_ssn.deny`, `hr_employee_data.export_bulk_pii.deny`, `inj.bulk_ssn` | 6 |

### MITRE ATLAS

| control | cases | count |
| --- | --- | --- |
| **T0010** | `code_deployment.deploy_unsigned.deny`, `code_deployment.deploy_unsigned_staging.deny` | 2 |
| **T0051** | `cloud_iam.attach_admin_policy.deny`, `inj.wildcard_grant`, `tc.escalate_after_read` | 3 |
| **T0054** | `cloud_iam.disable_mfa.deny`, `inj.disable_edr`, `security_response.disable_all_edr.deny`, `security_response.set_policy_permissive.deny` | 4 |

### Custom

| control | cases | count |
| --- | --- | --- |
| **CF-01** | `incident_rollback.execute_during_freeze.deny_after_timeout` | 1 |
| **CF-02** | `incident_rollback.hotfix_freeze.deny_after_timeout` | 1 |
| **DOS-01** | `security_response.block_all.deny` | 1 |
| **FR-01** | `finance_payment.pay_new_payee.deny_after_veto` | 1 |
| **FR-02** | `finance_payment.pay_over_ceiling.deny` | 1 |
| **OT-01** | `robotics_ot.actuate_over_limit.deny` | 1 |
| **OT-02** | `robotics_ot.actuate_high_pressure.deny` | 1 |
| **OT-03** | `robotics_ot.emergency_override.deny` | 1 |

## Summary

| framework | kind | controls | cases |
| --- | --- | --- | --- |
| EU AI Act | regulatory | 3 | 51 |
| NIST AI RMF | regulatory | 3 | 54 |
| ISO/IEC 42001 | regulatory | 3 | 19 |
| OWASP LLM Top 10 | threat | 2 | 10 |
| MITRE ATLAS | threat | 3 | 9 |
| Custom | threat | 8 | 8 |
