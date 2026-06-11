"""Pydantic schemas for the multi-account endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


class AccountSummary(BaseModel):
    """An account the current identity can access, with its role on it."""

    id: uuid.UUID
    name: str
    role: str
    is_default: bool = False


class AccountListResponse(BaseModel):
    """The list of accounts accessible to the current identity."""

    accounts: list[AccountSummary]


# ── Phase 3 : membres / invitations / audit ──────────────────────────────────


class MemberSummary(BaseModel):
    """A membership of an account, with the member's email and status."""

    membership_id: uuid.UUID
    identity_id: uuid.UUID
    email: str
    role: str
    status: str


class MemberListResponse(BaseModel):
    members: list[MemberSummary]


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str
    # 'collaborator' (défaut) : l'invité rejoint ce compte.
    # 'coach_link' : l'invité (client) accorde au coach un accès délégué sur SON
    # compte ; le rôle est alors forcé à COACH côté service.
    kind: str = "collaborator"


class InvitationResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    email: str
    role: str
    status: str
    kind: str = "collaborator"
    # token renvoyé pour faciliter le test/dev (l'email est best-effort).
    token: str
    expires_at: datetime


class InvitationListResponse(BaseModel):
    invitations: list[InvitationResponse]


class InvitationPreview(BaseModel):
    """Aperçu public d'une invitation (avant acceptation) pour l'écran de consentement."""

    email: str
    role: str
    kind: str
    status: str
    account_name: str
    inviter_email: str | None = None


class RoleChange(BaseModel):
    role: str | None = None
    status: str | None = None


class CoachInfo(BaseModel):
    """Le coach actif d'un compte client (côté client : voir / révoquer)."""

    membership_id: uuid.UUID | None = None
    email: str | None = None


class AuditEntry(BaseModel):
    id: uuid.UUID
    actor_identity_id: uuid.UUID | None
    action: str
    payload: dict[str, Any]
    created_at: datetime


class AuditListResponse(BaseModel):
    entries: list[AuditEntry]
