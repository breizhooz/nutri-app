"""Tests unitaires pour LocalizedHTTPException (app/i18n/exceptions.py)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.i18n.exceptions import LocalizedHTTPException


def _make_request(locale: str | None = None) -> MagicMock:
    req = MagicMock()
    req.state = SimpleNamespace() if locale is None else SimpleNamespace(locale=locale)
    return req


class TestLocalizedHTTPExceptionInit:
    @pytest.mark.unit
    def test_default_locale_is_fr(self):
        """Sans request.state.locale, la locale par défaut est 'fr'."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "message"
            LocalizedHTTPException(404, "some.key", req, code="C")
        mock_t.get.assert_called_once_with("some.key", locale="fr")

    @pytest.mark.unit
    def test_explicit_locale_used(self):
        """request.state.locale est pris en compte."""
        req = _make_request(locale="en")
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "message"
            LocalizedHTTPException(403, "some.key", req, code="C")
        mock_t.get.assert_called_once_with("some.key", locale="en")

    @pytest.mark.unit
    def test_message_none_detail_equals_base(self):
        """Sans message, detail == base traduit."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "base message"
            exc = LocalizedHTTPException(422, "some.key", req, code="C")
        assert exc.detail == "base message"

    @pytest.mark.unit
    def test_message_appended_to_base(self):
        """Avec message, detail == 'base : message'."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "base"
            exc = LocalizedHTTPException(
                500, "some.key", req, code="C", message="detail"
            )
        assert exc.detail == "base : detail"

    @pytest.mark.unit
    def test_status_code_set(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "msg"
            exc = LocalizedHTTPException(503, "some.key", req, code="C")
        assert exc.status_code == 503

    @pytest.mark.unit
    def test_code_attribute_set(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "msg"
            exc = LocalizedHTTPException(404, "key", req, code="MY_CODE")
        assert exc.code == "MY_CODE"

    @pytest.mark.unit
    def test_default_code_is_unknown(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "msg"
            exc = LocalizedHTTPException(404, "key", req)
        assert exc.code == "UNKNOWN"

    @pytest.mark.unit
    def test_kwargs_forwarded_to_translation(self):
        """Les kwargs supplémentaires sont transmis à t.get()."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "msg"
            LocalizedHTTPException(422, "key", req, code="C", param="value")
        mock_t.get.assert_called_once_with("key", locale="fr", param="value")


class TestLocalizedHTTPExceptionFactories:
    @pytest.mark.unit
    def test_recipe_not_found(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "not found"
            exc = LocalizedHTTPException.recipe_not_found(req)
        assert exc.status_code == 404
        assert exc.code == "RECIPE_NOT_FOUND"

    @pytest.mark.unit
    def test_unauthorized(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "forbidden"
            exc = LocalizedHTTPException.unauthorized(req)
        assert exc.status_code == 403
        assert exc.code == "RECIPE_UNAUTHORIZED"

    @pytest.mark.unit
    def test_ingredient_not_found(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "not found"
            exc = LocalizedHTTPException.ingredient_not_found(req)
        assert exc.status_code == 404
        assert exc.code == "INGREDIENT_NOT_FOUND"

    @pytest.mark.unit
    def test_slug_too_big(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "slug too big"
            exc = LocalizedHTTPException.slug_too_big(req)
        assert exc.status_code == 422
        assert exc.code == "RECIPE_SLUG_TOO_BIG"

    @pytest.mark.unit
    def test_ingredient_already_exist(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "exists"
            exc = LocalizedHTTPException.ingredient_already_exist(req)
        assert exc.status_code == 409
        assert exc.code == "INGREDIENT_ALREADY_EXISTS"

    @pytest.mark.unit
    def test_user_id_not_exists(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "user not found"
            exc = LocalizedHTTPException.user_id_not_exists(req)
        assert exc.status_code == 422
        assert exc.code == "USER_NOT_EXISTS"

    @pytest.mark.unit
    def test_service_user_unavailable(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "unavailable"
            exc = LocalizedHTTPException.service_user_unavailable(req)
        assert exc.status_code == 503
        assert exc.code == "SERVICE_USER_UNAVAILABLE"

    @pytest.mark.unit
    def test_service_es_failed_status_and_code(self):
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "ES error"
            exc = LocalizedHTTPException.service_es_failed(
                req, "es.errors.failed", RuntimeError("index error")
            )
        assert exc.status_code == 500
        assert exc.code == "ELASTICSEARCH_ERROR"

    @pytest.mark.unit
    def test_service_es_failed_exception_message_in_detail(self):
        """Le message de l'exception est inclus dans detail."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "ES error"
            exc = LocalizedHTTPException.service_es_failed(
                req, "es.errors.failed", ValueError("timeout")
            )
        assert "timeout" in exc.detail

    @pytest.mark.unit
    def test_service_es_failed_translation_key_forwarded(self):
        """service_es_failed transmet la clé de traduction donnée à t.get."""
        req = _make_request()
        with patch("app.i18n.exceptions.t") as mock_t:
            mock_t.get.return_value = "msg"
            LocalizedHTTPException.service_es_failed(
                req, "custom.es.key", RuntimeError("err")
            )
        mock_t.get.assert_called_once_with("custom.es.key", locale="fr")
