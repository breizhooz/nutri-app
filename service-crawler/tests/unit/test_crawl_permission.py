import uuid

import pytest
from fastapi import HTTPException

from app.core.deps import CrawlPermission, RequireCrawlRight, UniqLinkPermission


def _payload(admin=False, insta=False, web=False, sub=None):
    return {
        "sub": sub or str(uuid.uuid4()),
        "type": "access",
        "user_admin": admin,
        "user_right": {"crawl": {"instagram": insta, "web": web}},
    }


def test_admin_bypasses_all_sources():
    payload = _payload(admin=True)
    assert CrawlPermission.allowed(payload, "instagram") is True
    assert CrawlPermission.allowed(payload, "web") is True


def test_specific_right_grants_only_that_source():
    payload = _payload(web=True)
    assert CrawlPermission.allowed(payload, "web") is True
    assert CrawlPermission.allowed(payload, "instagram") is False


def test_missing_rights_defaults_to_denied():
    assert CrawlPermission.allowed({"sub": "x"}, "web") is False
    assert CrawlPermission.allowed({"sub": "x", "user_right": {}}, "web") is False


def test_ensure_raises_403_when_denied():
    with pytest.raises(HTTPException) as exc:
        CrawlPermission.ensure(_payload(), "web")
    assert exc.value.status_code == 403


def test_ensure_passes_when_allowed():
    # Ne doit pas lever
    CrawlPermission.ensure(_payload(web=True), "web")
    CrawlPermission.ensure(_payload(admin=True), "instagram")


@pytest.mark.asyncio
async def test_require_crawl_right_returns_user_id_when_allowed():
    sub = str(uuid.uuid4())
    dependency = RequireCrawlRight("web")
    result = await dependency(_payload(web=True, sub=sub))
    assert str(result) == sub


@pytest.mark.asyncio
async def test_require_crawl_right_forbidden_when_denied():
    dependency = RequireCrawlRight("instagram")
    with pytest.raises(HTTPException) as exc:
        await dependency(_payload(web=True))
    assert exc.value.status_code == 403


# ─── UniqLinkPermission (droit d'import par lien unique) ───────────────────────


def _uniq_payload(admin=False, insta=False, web=False):
    return {
        "sub": "u1",
        "type": "access",
        "user_admin": admin,
        "user_right": {"uniq_link": {"instagram": insta, "web": web}},
    }


def test_uniq_link_admin_bypasses():
    assert UniqLinkPermission.allowed(_uniq_payload(admin=True), "instagram") is True
    assert UniqLinkPermission.allowed(_uniq_payload(admin=True), "web") is True


def test_uniq_link_specific_right_only():
    assert UniqLinkPermission.allowed(_uniq_payload(web=True), "web") is True
    assert UniqLinkPermission.allowed(_uniq_payload(web=True), "instagram") is False


def test_uniq_link_missing_defaults_denied():
    assert UniqLinkPermission.allowed({"sub": "x"}, "web") is False
    # un droit crawl ne donne pas le droit uniq_link
    assert (
        UniqLinkPermission.allowed(
            {"sub": "x", "user_right": {"crawl": {"web": True}}}, "web"
        )
        is False
    )


def test_uniq_link_ensure_raises_403_when_denied():
    with pytest.raises(HTTPException) as exc:
        UniqLinkPermission.ensure(_uniq_payload(), "web")
    assert exc.value.status_code == 403
