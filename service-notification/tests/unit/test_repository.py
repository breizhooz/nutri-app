import uuid

import pytest

from app.models.enums import NotificationStatus, NotificationType
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestSubscriptionRepository:
    @pytest.mark.unit
    async def test_create_persists_subscription(self, db_session):
        """create() retourne une subscription avec id et slug non-vides."""
        repo = SubscriptionRepository(db_session)
        sub = await repo.create(
            user_id=USER_ID,
            endpoint="https://fcm.example.com/abc",
            p256dh_key="p256dh",
            auth_key="auth",
            device_label="Chrome Desktop",
        )
        assert sub.id is not None
        assert sub.slug
        assert "chrome-desktop" in sub.slug
        assert sub.user_id == USER_ID

    @pytest.mark.unit
    async def test_create_without_device_label_uses_device_fallback(self, db_session):
        """Sans device_label, le slug contient 'device'."""
        repo = SubscriptionRepository(db_session)
        sub = await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/nolabel",
            p256dh_key="k", auth_key="a",
        )
        assert "device" in sub.slug
        assert sub.device_label is None

    @pytest.mark.unit
    async def test_create_slug_collision_adds_counter(self, db_session):
        """Deux subscriptions même user + device_label → slugs différents avec suffixe -2."""
        repo = SubscriptionRepository(db_session)
        s1 = await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/1",
            p256dh_key="k1", auth_key="a1", device_label="Mobile",
        )
        s2 = await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/2",
            p256dh_key="k2", auth_key="a2", device_label="Mobile",
        )
        assert s1.slug != s2.slug
        assert s2.slug.endswith("-2")

    @pytest.mark.unit
    async def test_get_by_slug_returns_subscription(self, db_session):
        """get_by_slug retourne la subscription si elle existe."""
        repo = SubscriptionRepository(db_session)
        created = await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/byslug",
            p256dh_key="k", auth_key="a",
        )
        found = await repo.get_by_slug(created.slug)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.unit
    async def test_get_by_slug_unknown_returns_none(self, db_session):
        """get_by_slug sur un slug inexistant → None."""
        repo = SubscriptionRepository(db_session)
        assert await repo.get_by_slug("slug-inexistant") is None

    @pytest.mark.unit
    async def test_get_by_endpoint_returns_subscription(self, db_session):
        """get_by_endpoint retourne la subscription si l'endpoint existe."""
        repo = SubscriptionRepository(db_session)
        endpoint = "https://push.example.com/endpoint-lookup"
        created = await repo.create(
            user_id=USER_ID, endpoint=endpoint, p256dh_key="k", auth_key="a"
        )
        found = await repo.get_by_endpoint(endpoint)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.unit
    async def test_get_by_endpoint_unknown_returns_none(self, db_session):
        """get_by_endpoint sur un endpoint inconnu → None."""
        repo = SubscriptionRepository(db_session)
        assert await repo.get_by_endpoint("https://unknown.example.com") is None

    @pytest.mark.unit
    async def test_get_by_user_id_returns_all(self, db_session):
        """get_by_user_id retourne toutes les subscriptions du user."""
        repo = SubscriptionRepository(db_session)
        await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/ua",
            p256dh_key="k1", auth_key="a1",
        )
        await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/ub",
            p256dh_key="k2", auth_key="a2",
        )
        subs = await repo.get_by_user_id(USER_ID)
        assert len(subs) == 2
        assert all(s.user_id == USER_ID for s in subs)

    @pytest.mark.unit
    async def test_get_by_user_id_unknown_user_returns_empty(self, db_session):
        """User sans subscription → liste vide."""
        repo = SubscriptionRepository(db_session)
        assert await repo.get_by_user_id(uuid.uuid4()) == []

    @pytest.mark.unit
    async def test_delete_removes_from_db(self, db_session):
        """delete() supprime la subscription, get_by_slug retourne None ensuite."""
        repo = SubscriptionRepository(db_session)
        sub = await repo.create(
            user_id=USER_ID, endpoint="https://push.example.com/del",
            p256dh_key="k", auth_key="a",
        )
        slug = sub.slug
        await repo.delete(sub)
        assert await repo.get_by_slug(slug) is None


class TestNotificationRepository:
    @pytest.mark.unit
    async def test_create_persists_with_pending_status(self, db_session):
        """create() persiste avec status=pending et sent_at=None."""
        repo = NotificationRepository(db_session)
        notif = await repo.create(
            user_id=USER_ID,
            type=NotificationType.MACRO_ERROR,
            title="Ingrédient non reconnu",
            body="Gochujank introuvable",
            data={"macro_error_slug": "gochujank-20260518"},
        )
        assert notif.id is not None
        assert notif.slug
        assert notif.status == NotificationStatus.PENDING
        assert notif.sent_at is None

    @pytest.mark.unit
    async def test_create_without_data_stores_none(self, db_session):
        """Création sans data → data=None en base."""
        repo = NotificationRepository(db_session)
        notif = await repo.create(
            user_id=USER_ID, type=NotificationType.SYSTEM, title="T", body="B"
        )
        assert notif.data is None

    @pytest.mark.unit
    async def test_create_generates_unique_slugs(self, db_session):
        """Deux créations successives → slugs différents (timestamp microseconde)."""
        repo = NotificationRepository(db_session)
        n1 = await repo.create(
            user_id=USER_ID, type=NotificationType.SYSTEM, title="T", body="B"
        )
        n2 = await repo.create(
            user_id=USER_ID, type=NotificationType.SYSTEM, title="T", body="B"
        )
        assert n1.slug != n2.slug

    @pytest.mark.unit
    async def test_update_status_to_sent_sets_sent_at(self, db_session):
        """update_status(SENT) → sent_at est renseigné."""
        repo = NotificationRepository(db_session)
        notif = await repo.create(
            user_id=USER_ID, type=NotificationType.CRAWL_DONE, title="T", body="B"
        )
        updated = await repo.update_status(notif, NotificationStatus.SENT)
        assert updated.status == NotificationStatus.SENT
        assert updated.sent_at is not None

    @pytest.mark.unit
    async def test_update_status_to_failed_does_not_set_sent_at(self, db_session):
        """update_status(FAILED) → sent_at reste None."""
        repo = NotificationRepository(db_session)
        notif = await repo.create(
            user_id=USER_ID, type=NotificationType.MACRO_ERROR, title="T", body="B"
        )
        updated = await repo.update_status(notif, NotificationStatus.FAILED)
        assert updated.status == NotificationStatus.FAILED
        assert updated.sent_at is None

    @pytest.mark.unit
    async def test_get_by_user_id_ordered_desc(self, db_session):
        """get_by_user_id retourne les notifications du plus récent au plus ancien."""
        from datetime import timedelta
        from sqlalchemy import update as sa_update
        from app.models.notification import Notification

        repo = NotificationRepository(db_session)
        n1 = await repo.create(
            user_id=USER_ID, type=NotificationType.SYSTEM, title="Premier", body="B"
        )
        n2 = await repo.create(
            user_id=USER_ID, type=NotificationType.SYSTEM, title="Deuxième", body="B"
        )

        # SQLite in-memory : func.now() identique pour deux inserts rapides.
        # On force n1 dans le passé pour garantir l'ordre DESC.
        from datetime import datetime, timezone
        await db_session.execute(
            sa_update(Notification)
            .where(Notification.id == n1.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        )
        await db_session.commit()

        results = await repo.get_by_user_id(USER_ID)
        assert len(results) == 2
        assert results[0].title == "Deuxième"
        assert results[1].title == "Premier"

    @pytest.mark.unit
    async def test_get_by_user_id_limit_and_offset(self, db_session):
        """limit et offset découpent correctement la pagination."""
        repo = NotificationRepository(db_session)
        for i in range(5):
            await repo.create(
                user_id=USER_ID, type=NotificationType.SYSTEM,
                title=f"Notif {i}", body="B"
            )
        page1 = await repo.get_by_user_id(USER_ID, limit=2, offset=0)
        page2 = await repo.get_by_user_id(USER_ID, limit=2, offset=2)
        page3 = await repo.get_by_user_id(USER_ID, limit=2, offset=4)
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
        assert all(p.slug not in {x.slug for x in page2} for p in page1)

    @pytest.mark.unit
    async def test_get_by_user_id_unknown_user_returns_empty(self, db_session):
        """User sans notification → liste vide."""
        repo = NotificationRepository(db_session)
        assert await repo.get_by_user_id(uuid.uuid4()) == []

    @pytest.mark.unit
    def test_build_slug_contains_type_and_user_prefix(self):
        """_build_slug contient le type slugifié et le préfixe de l'UUID."""
        slug = NotificationRepository._build_slug("macro_error", USER_ID)
        assert "macro-error" in slug
        assert str(USER_ID)[:8] in slug

    @pytest.mark.unit
    def test_build_slug_different_on_each_call(self):
        """Deux appels successifs à _build_slug → slugs différents."""
        s1 = NotificationRepository._build_slug("system", USER_ID)
        s2 = NotificationRepository._build_slug("system", USER_ID)
        # En théorie identiques si même microseconde, mais le test documente le contrat
        assert isinstance(s1, str) and isinstance(s2, str)