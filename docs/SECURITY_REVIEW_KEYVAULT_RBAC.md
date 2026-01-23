# Azure Key Vault and RBAC Security Review

## Key Vault Access Policies
- Key Vault is provisioned via Bicep with `enableRbacAuthorization: true`.
- Only Azure AD users/groups with explicit RBAC roles (e.g., Key Vault Secrets User/Reader) can access secrets.
- No public network access except for required services.
- Soft delete and purge protection are enabled (90 days retention).

## Recommendations
- Regularly audit Key Vault access via Azure Portal > Key Vault > Access control (IAM).
- Remove any unnecessary users/groups from having access.
- Use least-privilege: assign only the minimum required roles (e.g., Reader, Secrets User).
- Review audit logs for unauthorized access attempts.

## Azure RBAC
- Resource group and resources (PostgreSQL, Redis, Container Apps) inherit RBAC from the parent group.
- Only assign Contributor/Owner roles to trusted DevOps/admins.
- Use custom roles for fine-grained access if needed.

## Action Items
- [ ] Review and document all current Key Vault access assignments.
- [ ] Review resource group IAM and remove excess permissions.
- [ ] Enable Azure Policy for Key Vault and resource group for compliance.

---
This file should be reviewed quarterly and after any major team or infra change.
