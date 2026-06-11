"""Domain errors for the multi-account admin layer (invitations / members).

Les routes attrapent :class:`AccountAccessError` et la traduisent en réponse HTTP
(``status_code`` + clé i18n ``detail_key``).
"""


class AccountAccessError(Exception):
    """Base : porte un status HTTP et une clé i18n."""

    status_code: int = 400
    detail_key: str = "accounts.error"


class RankTooHigh(AccountAccessError):
    status_code = 403
    detail_key = "accounts.rank_too_high"


class LastOwner(AccountAccessError):
    status_code = 409
    detail_key = "accounts.last_owner"


class MembershipNotFound(AccountAccessError):
    status_code = 404
    detail_key = "accounts.membership_not_found"


class AlreadyMember(AccountAccessError):
    status_code = 409
    detail_key = "accounts.already_member"


class InvitationInvalid(AccountAccessError):
    status_code = 400
    detail_key = "accounts.invitation_invalid"


class InvitationEmailMismatch(AccountAccessError):
    status_code = 403
    detail_key = "accounts.invitation_email_mismatch"


class InvitationNotFound(AccountAccessError):
    status_code = 404
    detail_key = "accounts.invitation_not_found"


class CoachAlreadyAssigned(AccountAccessError):
    """Un coach actif existe déjà sur ce compte client (1 coach max)."""

    status_code = 409
    detail_key = "accounts.coach_already_assigned"


class CannotCoachSelf(AccountAccessError):
    """Le coach et le client sont la même identité."""

    status_code = 400
    detail_key = "accounts.cannot_coach_self"


class NoClientAccount(AccountAccessError):
    """Le client accepteur n'a pas de compte par défaut où greffer le coach."""

    status_code = 409
    detail_key = "accounts.no_client_account"
