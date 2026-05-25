"""Tests unitaires — schemas CrawlSource (union discriminée)."""

import pytest
from datetime import time
from pydantic import ValidationError

from app.models.enums import CrawlType
from app.schemas.crawl_source import (
    CrawlSourceCreate,
    InstagramSourceCreate,
    WebSourceCreate,
)

# ─── WebSourceCreate ──────────────────────────────────────────────────────────


def test_web_source_accepts_valid_http_url():
    s = WebSourceCreate(type=CrawlType.WEB, url="https://example.com/recipe")
    assert s.url == "https://example.com/recipe"


def test_web_source_accepts_http_scheme():
    s = WebSourceCreate(type=CrawlType.WEB, url="http://example.com")
    assert s.url == "http://example.com"


def test_web_source_rejects_plain_string():
    with pytest.raises(ValidationError):
        WebSourceCreate(type=CrawlType.WEB, url="not-a-url")


def test_web_source_rejects_ftp_url():
    with pytest.raises(ValidationError):
        WebSourceCreate(type=CrawlType.WEB, url="ftp://example.com/file")


def test_web_source_default_frequency():
    s = WebSourceCreate(type=CrawlType.WEB, url="https://example.com")
    assert s.frequency_hours == 24
    assert s.execution_hour == time(3, 0)


def test_web_source_model_dump_contains_url_key():
    s = WebSourceCreate(type=CrawlType.WEB, url="https://example.com")
    dumped = s.model_dump()
    assert "url" in dumped
    assert dumped["url"] == "https://example.com"


# ─── InstagramSourceCreate ────────────────────────────────────────────────────


def test_instagram_source_normalizes_at_prefix():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="@chef_paul")
    assert s.account == "chef_paul"


def test_instagram_source_accepts_account_without_at():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="chef_paul")
    assert s.account == "chef_paul"


def test_instagram_source_strips_multiple_at():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="@@chef")
    assert s.account == "chef"


def test_instagram_source_rejects_empty_account():
    with pytest.raises(ValidationError):
        InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="")


def test_instagram_source_rejects_at_only():
    with pytest.raises(ValidationError):
        InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="@")


def test_instagram_source_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="   ")


def test_instagram_source_model_dump_maps_account_to_url():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="@chef_paul")
    dumped = s.model_dump()
    assert "url" in dumped
    assert dumped["url"] == "chef_paul"
    assert "account" not in dumped


def test_instagram_source_model_dump_preserves_type():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="chef")
    dumped = s.model_dump()
    assert dumped["type"] == CrawlType.INSTAGRAM


def test_instagram_source_default_frequency():
    s = InstagramSourceCreate(type=CrawlType.INSTAGRAM, account="chef")
    assert s.frequency_hours == 24
    assert s.execution_hour == time(3, 0)


# ─── Union discriminée CrawlSourceCreate ─────────────────────────────────────


def test_union_dispatches_to_web_on_type_web():
    from pydantic import TypeAdapter

    adapter = TypeAdapter(CrawlSourceCreate)
    parsed = adapter.validate_python({"type": "web", "url": "https://example.com"})
    assert isinstance(parsed, WebSourceCreate)


def test_union_dispatches_to_instagram_on_type_instagram():
    from pydantic import TypeAdapter

    adapter = TypeAdapter(CrawlSourceCreate)
    parsed = adapter.validate_python({"type": "instagram", "account": "@chef"})
    assert isinstance(parsed, InstagramSourceCreate)


def test_union_rejects_unknown_type():
    from pydantic import TypeAdapter

    adapter = TypeAdapter(CrawlSourceCreate)
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "youtube", "url": "https://youtube.com/@chef"})
