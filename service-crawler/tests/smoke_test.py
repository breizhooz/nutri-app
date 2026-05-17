import time
import httpx
import pytest

SERVICE_CRAWLER_URL = "http://localhost:8004"
_NULL_UUID = "00000000-0000-0000-0000-000000000000"
_RESULTS_URL = f"{SERVICE_CRAWLER_URL}/api/v1/crawler/results"


class ResultsSmokeHelper:
    @staticmethod
    def get_paginated(client: httpx.Client, **params) -> httpx.Response:
        return client.get(_RESULTS_URL, params=params)

    @staticmethod
    def get_one(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.get(f"{_RESULTS_URL}/{result_id}")

    @staticmethod
    def patch_result(client: httpx.Client, result_id: str, payload: dict) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}", json=payload)

    @staticmethod
    def validate(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}/validate")

    @staticmethod
    def reject(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}/reject")

    @staticmethod
    def poll_for_result(
        client: httpx.Client,
        source_id: str,
        timeout: int = 30,
        interval: float = 2.0,
    ) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = client.get(_RESULTS_URL, params={"status": "waiting", "source_id": source_id})
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    return items[0]
            time.sleep(interval)
        return None


@pytest.fixture()
def source_setup():
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "web",
            "url": "https://smoke-test.example.com",
            "frequency_hours": 24,
        })
        assert response.status_code == 201, f"Erreur création source: {response.text}"
        source_id = response.json()["id"]

    yield source_id

    with httpx.Client() as client:
        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


@pytest.fixture()
def crawled_result_setup():
    import uuid as _uuid
    unique_url = f"https://www.marmiton.org/recettes/recette_tarte-aux-pommes_12372.aspx?smoke={_uuid.uuid4().hex}"

    with httpx.Client(timeout=60.0) as client:
        create = client.post(
            f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources",
            json={"type": "web", "url": unique_url},
        )
        assert create.status_code == 201, f"Création source échouée: {create.text}"
        source_id = create.json()["id"]

        trigger = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
        assert trigger.status_code == 202, f"Trigger crawl échoué: {trigger.text}"

        result = ResultsSmokeHelper.poll_for_result(client, source_id, timeout=60)

        if result is None:
            client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")
            pytest.skip("Worker Celery injoignable ou crawl échoué — stack incomplète")

        yield result

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_crawler_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "service-crawler"


@pytest.mark.smoke
def test_crawler_health_db():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Sources ────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_create_web_source():
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "web",
            "url": "https://create-test.example.com",
        })
        assert response.status_code == 201
        body = response.json()
        assert body["url"] == "https://create-test.example.com"
        assert body["type"] == "web"
        assert body["actif"] is True
        assert "id" in body

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{body['id']}")


@pytest.mark.smoke
def test_source_lifecycle(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        get = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")
        assert get.status_code == 200
        assert get.json()["id"] == source_id

        patch = client.patch(
            f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}",
            json={"actif": False, "frequency_hours": 48},
        )
        assert patch.status_code == 200
        assert patch.json()["actif"] is False
        assert patch.json()["frequency_hours"] == 48


@pytest.mark.smoke
def test_list_sources_contains_created(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert source_id in ids


@pytest.mark.smoke
def test_trigger_crawl_queued(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
    assert response.status_code == 202
    body = response.json()
    assert "source_id" in body
    assert "task_id" in body


@pytest.mark.smoke
def test_trigger_crawl_unsupported_type():
    with httpx.Client() as client:
        create = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "instagram",
            "url": "@smoke_test_account",
        })
        assert create.status_code == 201
        source_id = create.json()["id"]

        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
        assert response.status_code == 400

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


@pytest.mark.smoke
def test_get_source_not_found():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{_NULL_UUID}")
    assert response.status_code == 404


# ── Résultats — listing paginé ─────────────────────────────────────────────────

@pytest.mark.smoke
def test_list_results_returns_paginated_envelope():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.smoke
def test_list_results_default_status_is_waiting():
    with httpx.Client() as client:
        r1 = ResultsSmokeHelper.get_paginated(client)
        r2 = ResultsSmokeHelper.get_paginated(client, status="waiting")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["total"] == r2.json()["total"]


@pytest.mark.smoke
def test_list_results_filter_by_valid_status():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, status="valid")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["status"] == "valid"


@pytest.mark.smoke
def test_list_results_filter_by_rejected_status():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, status="rejected")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["status"] == "rejected"


@pytest.mark.smoke
def test_list_results_pagination_params():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page=1, page_size=5)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5


@pytest.mark.smoke
def test_list_results_page_size_above_max_rejected():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page_size=200)
    assert response.status_code == 422


@pytest.mark.smoke
def test_list_results_page_zero_rejected():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page=0)
    assert response.status_code == 422


@pytest.mark.smoke
def test_list_results_filter_by_source_id_empty():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, source_id=_NULL_UUID, status="waiting")
    assert response.status_code == 200
    assert response.json()["total"] == 0


# ── Résultats — détail ─────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_get_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_one(client, _NULL_UUID)
    assert response.status_code == 404


@pytest.mark.smoke
def test_get_result_invalid_uuid():
    with httpx.Client() as client:
        response = client.get(f"{_RESULTS_URL}/not-a-uuid")
    assert response.status_code == 422


# ── Résultats — guards 404 sans résultat réel ──────────────────────────────────

@pytest.mark.smoke
def test_validate_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.validate(client, _NULL_UUID)
    assert response.status_code == 404


@pytest.mark.smoke
def test_reject_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.reject(client, _NULL_UUID)
    assert response.status_code == 404


@pytest.mark.smoke
def test_patch_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.patch_result(client, _NULL_UUID, {"title": "X"})
    assert response.status_code == 404


# ── Résultats — flux complets (nécessite Celery worker) ───────────────────────

@pytest.mark.smoke
@pytest.mark.integration
def test_get_crawled_result_detail(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_one(client, result["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == result["id"]
    assert body["status"] == "waiting"
    assert body["url_origin"] != ""


@pytest.mark.smoke
@pytest.mark.integration
def test_edit_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.patch_result(
            client, result["id"], {"title": "Titre corrigé smoke test"}
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Titre corrigé smoke test"


@pytest.mark.smoke
@pytest.mark.integration
def test_reject_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.reject(client, result["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.smoke
@pytest.mark.integration
def test_cannot_edit_after_rejection(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.reject(client, result["id"])
        response = ResultsSmokeHelper.patch_result(client, result["id"], {"title": "X"})
    assert response.status_code == 409


@pytest.mark.smoke
@pytest.mark.integration
def test_cannot_reject_twice(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.reject(client, result["id"])
        response = ResultsSmokeHelper.reject(client, result["id"])
    assert response.status_code == 409


@pytest.mark.smoke
@pytest.mark.integration
def test_validate_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.validate(client, result["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["validate_by"] is not None


@pytest.mark.smoke
@pytest.mark.integration
def test_cannot_edit_after_validation(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.patch_result(client, result["id"], {"title": "X"})
    assert response.status_code == 409


@pytest.mark.smoke
@pytest.mark.integration
def test_cannot_validate_twice(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.validate(client, result["id"])
    assert response.status_code == 409


@pytest.mark.smoke
@pytest.mark.integration
def test_validated_result_appears_in_valid_filter(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.get_paginated(client, status="valid")
    ids = [item["id"] for item in response.json()["items"]]
    assert result["id"] in ids


# ── Settings ───────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_crawler_settings_get():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings")
    assert response.status_code == 200
    body = response.json()
    assert "js_detection_threshold" in body
    assert isinstance(body["js_detection_threshold"], int)


@pytest.mark.smoke
def test_crawler_settings_update():
    with httpx.Client() as client:
        original = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings").json()["js_detection_threshold"]

        response = client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": 300})
        assert response.status_code == 200
        assert response.json()["js_detection_threshold"] == 300

        get = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings")
        assert get.json()["js_detection_threshold"] == 300

        client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": original})


@pytest.mark.smoke
def test_crawler_settings_rejects_invalid_threshold():
    with httpx.Client() as client:
        response = client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": 5})
    assert response.status_code == 422
