import pytest
from app.i18n.loader import t


def test_get_existing_key_fr():
    result = t.get("crawl_source.not_found", locale="fr")
    assert result == "Source introuvable."


def test_get_existing_key_en():
    result = t.get("crawl_source.not_found", locale="en")
    assert result == "Source not found."


def test_get_missing_key_returns_key():
    result = t.get("does.not.exist", locale="fr")
    assert result == "does.not.exist"


def test_get_missing_locale_returns_key():
    result = t.get("crawl_source.not_found", locale="es")
    assert result == "crawl_source.not_found"


def test_get_all_crawl_source_keys():
    for key in ["not_found", "created", "updated", "deleted", "crawl_queued"]:
        assert t.get(f"crawl_source.{key}") != f"crawl_source.{key}"


def test_get_all_crawl_result_keys():
    for key in ["not_found", "updated", "validated", "rejected"]:
        assert t.get(f"crawl_result.{key}") != f"crawl_result.{key}"


def test_get_enum_crawl_type():
    assert t.get("enums.crawl_type.web") == "Web"
    assert t.get("enums.crawl_type.instagram") == "Instagram"


def test_get_enum_crawl_status():
    assert t.get("enums.crawl_status.waiting") == "En attente"
    assert t.get("enums.crawl_status.valid") == "Validé"
    assert t.get("enums.crawl_status.rejected") == "Rejeté"