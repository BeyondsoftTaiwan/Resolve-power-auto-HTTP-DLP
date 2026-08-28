"""Shared managed-identity configuration.

A Function App can have a system-assigned identity, one or more user-assigned
identities, or both. A credential constructed without a client ID always
resolves to the *system-assigned* identity, which may not exist, and which is
not necessarily the identity that was granted access to downstream resources.

Setting `MANAGED_IDENTITY_CLIENT_ID` (or the conventional `AZURE_CLIENT_ID`)
to the client ID of a user-assigned identity makes the choice explicit, so
storage and Azure DevOps are both reached as the same principal.
"""
from __future__ import annotations

import os

CLIENT_ID_SETTINGS = ("MANAGED_IDENTITY_CLIENT_ID", "AZURE_CLIENT_ID")


def managed_identity_client_id() -> str | None:
    """Return the configured user-assigned client ID, or None for system-assigned."""
    for name in CLIENT_ID_SETTINGS:
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
