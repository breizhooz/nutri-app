"""Traduction EN→FR d'un payload de recette Spoonacular (best-effort).

Spoonacular ne renvoie que de l'anglais. On traduit donc au moment du fetch et on
stocke la version française dans le cache, via deep-translator (Google, sans clé).

Champs traduits : titre, résumé, instructions, et pour chaque ingrédient
``original`` / ``name`` / ``nameClean`` + chaque étape de ``analyzedInstructions``.

Volontairement NON traduits : ``dishTypes`` et ``cuisines`` — le mapper s'en sert
pour déduire ``course_type`` / ``cuisine_origin`` à partir de clés anglaises ;
les traduire casserait ce mapping.

Best-effort : toute erreur (réseau, quota, lib absente) renvoie le payload
d'origine (anglais) et loggue un avertissement — le job quotidien ne plante pas.
"""

import copy
import logging

from app.core.config import settings
from app.services.spoonacular_mapper import strip_html

logger = logging.getLogger(__name__)


class RecipeTranslator:
    def __init__(
        self,
        target: str = "fr",
        source: str = "en",
        enabled: bool | None = None,
        translate_batch=None,
    ) -> None:
        self._target = target
        self._source = source
        self._enabled = (
            settings.SPOONACULAR_TRANSLATE if enabled is None else enabled
        )
        # Injection d'une fonction list[str] -> list[str] (tests) ; sinon Google.
        self._translate_batch = translate_batch

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _batch(self, texts: list[str]) -> list[str]:
        if self._translate_batch is not None:
            return self._translate_batch(texts)
        from deep_translator import GoogleTranslator

        return GoogleTranslator(
            source=self._source, target=self._target
        ).translate_batch(texts)

    def translate_payload(self, payload: dict) -> dict:
        """Renvoie une copie FR du payload (ou l'original si désactivé/erreur)."""
        if not self._enabled or not payload:
            return payload

        p = copy.deepcopy(payload)

        # Feuilles texte à traduire : (conteneur, clé, is_html).
        leaves: list[tuple[dict, str, bool]] = []

        def add(container: dict, key: str, is_html: bool = False) -> None:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                leaves.append((container, key, is_html))

        add(p, "title")
        add(p, "summary", True)
        add(p, "instructions", True)
        for ing in p.get("extendedIngredients") or []:
            if isinstance(ing, dict):
                for k in ("original", "name", "nameClean"):
                    add(ing, k)
        for block in p.get("analyzedInstructions") or []:
            for step in block.get("steps") or []:
                if isinstance(step, dict):
                    add(step, "step")

        if not leaves:
            return p

        # Normalise le HTML en texte brut en place puis collecte les sources uniques.
        for container, key, is_html in leaves:
            if is_html:
                container[key] = strip_html(container[key])
        sources = list(dict.fromkeys(container[key] for container, key, _ in leaves))

        try:
            translated = self._batch(sources)
        except Exception as exc:  # noqa: BLE001 — best-effort, on garde l'anglais
            logger.warning(
                "Traduction Spoonacular échouée (%s) — payload EN conservé", exc
            )
            return payload

        mapping = dict(zip(sources, translated))
        for container, key, _ in leaves:
            container[key] = mapping.get(container[key]) or container[key]
        return p
