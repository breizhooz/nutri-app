"""Tests unitaires pour les tâches Celery nutrition."""

from unittest.mock import patch

import pytest


class TestImportCiquaTask:
    @pytest.mark.unit
    def test_import_ciqual_returns_imported_count(self):
        """import_ciqual retourne {"imported": N} après un import réussi."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=42):
            from app.tasks.nutrition_task import import_ciqual

            result = import_ciqual()

        assert result == {"imported": 42}

    @pytest.mark.unit
    def test_import_ciqual_zero_when_run_returns_zero(self):
        """import_ciqual retourne {"imported": 0} si asyncio.run retourne 0."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=0):
            from app.tasks.nutrition_task import import_ciqual

            result = import_ciqual()

        assert result == {"imported": 0}

    @pytest.mark.unit
    def test_enrich_from_off_returns_enriched_count(self):
        """enrich_from_off retourne {"enriched": N}."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=7):
            from app.tasks.nutrition_task import enrich_from_off

            result = enrich_from_off()

        assert result == {"enriched": 7}

    @pytest.mark.unit
    def test_enrich_from_off_zero_when_nothing_to_enrich(self):
        """enrich_from_off retourne {"enriched": 0} si aucun item n'est enrichi."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=0):
            from app.tasks.nutrition_task import enrich_from_off

            result = enrich_from_off()

        assert result == {"enriched": 0}

    @pytest.mark.unit
    def test_reindex_elasticsearch_returns_indexed_count(self):
        """reindex_elasticsearch retourne {"indexed": N}."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=150):
            from app.tasks.nutrition_task import reindex_elasticsearch

            result = reindex_elasticsearch()

        assert result == {"indexed": 150}

    @pytest.mark.unit
    def test_reindex_elasticsearch_zero_when_empty(self):
        """reindex_elasticsearch retourne {"indexed": 0} si la base est vide."""
        with patch("app.tasks.nutrition_task.asyncio.run", return_value=0):
            from app.tasks.nutrition_task import reindex_elasticsearch

            result = reindex_elasticsearch()

        assert result == {"indexed": 0}
