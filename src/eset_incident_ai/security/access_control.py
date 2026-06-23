from __future__ import annotations


class AccessControl:
    def can_access_tenant(self, *, principal_tenants: set[str], tenant_scope: str) -> bool:
        return tenant_scope in principal_tenants
