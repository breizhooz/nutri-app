from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings
from app.services.spacy_extractor import ExtractedIngredient

logger = logging.getLogger(__name__)


class GroqExtractor:
    """Extraction d'ingrédients via Groq API (Llama 3.1 8B, fallback gratuit).

    Le client httpx est injectable pour les tests.
    """

    _SYSTEM_PROMPT = (
        "Tu extrais des ingrédients d'une recette. "
        "Retourne UNIQUEMENT un tableau JSON d'objets avec les champs : "
        '{"quantite": float, "unite": string, "nom": string}. '
        "Ne retourne rien d'autre que le JSON."
    )

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(
            base_url="https://api.groq.com",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            timeout=30.0,
        ) as client:
            yield client

    async def extract(self, text: str) -> list[ExtractedIngredient]:
        """Retourne les ingrédients extraits. Lève ValueError si la réponse est invalide."""
        async with self._client() as client:
            resp = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": self._SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"]
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Groq a retourné un JSON invalide : {content}") from exc

        results = []
        for item in raw:
            try:
                results.append(
                    ExtractedIngredient(
                        raw_text=text,
                        quantite=float(item["quantite"]),
                        unite=str(item.get("unite", "g")).lower().strip(),
                        nom=str(item["nom"]).strip(),
                        confidence=0.85,
                    )
                )
            except (KeyError, ValueError):
                continue
        return results