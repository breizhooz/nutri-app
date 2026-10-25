import logging
from collections.abc import Callable
from typing import Any

from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import RecipeScrapersExceptions

logger = logging.getLogger(__name__)


class RecipeSchemaExtractor:
    """Extrait une recette publiée en données structurées (schema.org/Recipe en
    JSON-LD, Microdata ou RDFa) directement depuis le HTML, sans navigateur.

    La plupart des sites de recettes l'embarquent dans le HTML initial pour le
    référencement — y compris des sites rendus en JavaScript, dont le texte
    visible est vide côté httpx. ``recipe-scrapers`` travaille hors ligne
    (``online=False``) : aucune requête réseau, donc pas de surface SSRF.

    Le résultat reste du texte : les ingrédients ne sont pas découpés
    (quantité/unité/nom), ce qui reste le travail de l'hydratation Groq. Le texte
    produit est simplement propre et compact (une ligne par ingrédient).
    """

    def extract(self, url: str, html: str) -> dict | None:
        """Retourne ``{title, raw_content, images, video_url}`` ou ``None`` si la
        page ne publie pas de recette exploitable (ni ingrédients ni étapes)."""
        try:
            scraper = scrape_html(html, org_url=url, supported_only=False)
        except RecipeScrapersExceptions:
            return None
        except Exception as exc:  # lib tierce sur du HTML arbitraire
            logger.warning("recipe-scrapers a échoué sur %s : %s", url, exc)
            return None

        ingredients = self._field(scraper.ingredients) or []
        steps = self._field(scraper.instructions_list) or []
        if not ingredients and not steps:
            return None

        title = self._field(scraper.title) or ""
        image = self._field(scraper.image)
        raw_content = self._format(
            title=title,
            description=self._field(scraper.description),
            servings=self._field(scraper.yields),
            prep_minutes=self._field(scraper.prep_time),
            cook_minutes=self._field(scraper.cook_time),
            ingredients=ingredients,
            steps=steps,
        )
        logger.info("Recette schema.org trouvée pour %s", url)
        return {
            "title": title,
            "raw_content": raw_content,
            "images": [image] if isinstance(image, str) and image else [],
            "video_url": None,
        }

    @staticmethod
    def _field(getter: Callable[[], Any]) -> Any:
        """Lit un champ optionnel : un site peut ne pas le fournir (exception)."""
        try:
            return getter()
        except Exception:
            return None

    @staticmethod
    def _format(
        *,
        title: str,
        description: str | None,
        servings: str | None,
        prep_minutes: int | None,
        cook_minutes: int | None,
        ingredients: list[str],
        steps: list[str],
    ) -> str:
        # Étapes préfixées « Étape N : » (et non « N. ») pour ne pas être prises
        # pour des lignes d'ingrédient par le parseur quantité/unité du mapper.
        parts: list[str] = []
        if title:
            parts.append(title)
        if description:
            parts.append(description)
        infos = []
        if servings:
            infos.append(f"Portions : {servings}")
        if prep_minutes:
            infos.append(f"Préparation : {prep_minutes} min")
        if cook_minutes:
            infos.append(f"Cuisson : {cook_minutes} min")
        if infos:
            parts.append("\n".join(infos))
        if ingredients:
            parts.append("Ingrédients :\n" + "\n".join(f"- {i}" for i in ingredients))
        if steps:
            parts.append(
                "Instructions :\n"
                + "\n".join(f"Étape {n} : {s}" for n, s in enumerate(steps, 1))
            )
        return "\n\n".join(parts)
