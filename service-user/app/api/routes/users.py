import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_admin, get_current_user, get_locale
from app.core.security import hash_password, verify_password
from app.i18n.loader import t
from app.db.session import get_session
from app.models.user import User
from app.repositories.access_repository import MembershipRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password import PasswordChangeSchema, PasswordResetMessage
from app.schemas.user import UserAdminOut, UserCreate, UserOut, UserRightsUpdate
from app.services.access_service import AccessService
from app.services.export_service import ExportService
from app.services.password_reset_service import PasswordResetService
from app.services.user_service import UserService

router = APIRouter()


class UserServiceFactory:
    """FastAPI dependency factory wiring UserService with its repository."""

    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> UserService:
        return UserService(UserRepository(session))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("user.email_already_registered", get_locale(request)),
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    session.add(user)
    await session.flush()  # assign user.id before provisioning its account
    # Multicomptes : tout nouvel inscrit reçoit son compte personnel + OWNER.
    await AccessService(session).provision_personal_account(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),  # ← injecte l'user connecté
):
    return current_user


@router.get("/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Export RGPD (art. 20) : agrège les données personnelles de l'utilisateur.

    Rassemble l'identité (service-user) et les données détenues par les autres
    microservices (profil/santé, menus, notifications, nutrition) en un seul
    document JSON portable.
    """
    return await ExportService(session).build_export(current_user)


@router.post(
    "/me/password", response_model=PasswordResetMessage, status_code=status.HTTP_200_OK
)
async def change_password(
    request: Request,
    data: PasswordChangeSchema,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PasswordResetMessage:
    locale = get_locale(request)
    if not current_user.hashed_password or not verify_password(
        data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("password.current_incorrect", locale),
        )
    service = PasswordResetService(session)
    if await service.is_password_reused(
        current_user, data.new_password, settings.PASSWORD_HISTORY_COUNT
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get(
                "password.reuse_forbidden",
                locale,
                count=settings.PASSWORD_HISTORY_COUNT,
            ),
        )
    await service.update_password(current_user, data.new_password)
    return PasswordResetMessage(message=t.get("password.reset_success", locale))


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    request: Request,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("auth.forbidden", get_locale(request)),
        )
    return current_user


@router.get("", response_model=list[UserAdminOut])
async def list_users(
    _admin: User = Depends(get_current_admin),
    service: UserService = Depends(UserServiceFactory.inject),
    session: AsyncSession = Depends(get_session),
) -> list[UserAdminOut]:
    """List all users with their RBAC rights + account roles. Admin-only."""
    users = await service.list_users()
    roles = await MembershipRepository(session).roles_by_identity()
    return [
        UserAdminOut(
            id=u.id,
            email=u.email,
            is_active=u.is_active,
            user_admin=u.user_admin,
            is_coach=u.is_coach,
            account_roles=sorted(roles.get(u.id, [])),
            user_right=u.user_right,
        )
        for u in users
    ]


@router.patch("/{user_id}/rights", response_model=UserAdminOut)
async def update_user_rights(
    request: Request,
    user_id: uuid.UUID,
    payload: UserRightsUpdate,
    _admin: User = Depends(get_current_admin),
    service: UserService = Depends(UserServiceFactory.inject),
) -> User:
    """Update another user's RBAC rights (admin/crawl). Admin-only."""
    updated = await service.update_user_rights(user_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("user.not_found", get_locale(request)),
        )
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(UserServiceFactory.inject),
):
    """Delete a user account. Allowed for the account owner or any admin."""
    if current_user.id != user_id and not current_user.user_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("auth.forbidden", get_locale(request)),
        )
    deleted = await service.delete_user(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("user.not_found", get_locale(request)),
        )


@router.get("/{user_id}/exists")
async def is_user_exist(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, bool]:
    """
    Endpoint to check if user id exist in service user.

    return {"exist": true/false} without other data
    """
    result = await session.execute(select(User.id).where(User.id == user_id))
    user_exist = result.scalar_one_or_none() is not None

    return {"exists": user_exist}


@router.get("/{user_id}/default-account")
async def get_default_account(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, str | None]:
    """Résout le compte personnel (default_account_id) d'une identité.

    Endpoint inter-service (multicomptes) : permet aux flux pilotés par un token
    de service (crawler, import) de retrouver le compte sur lequel attribuer une
    ressource créée pour le compte de ``user_id``. Renvoie ``{"account_id": null}``
    si l'utilisateur n'existe pas ou n'a pas (encore) de compte.
    """
    result = await session.execute(
        select(User.default_account_id).where(User.id == user_id)
    )
    account_id = result.scalar_one_or_none()
    return {"account_id": str(account_id) if account_id else None}
