from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass

import httpx
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level Redis client (one connection pool per process)
_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_CACHE_URL, decode_responses=True
        )
    return _redis_client


@dataclass
class ExtractedRecipe:
    title: str
    instructions: str
    ingredients: list[dict]
    tokens_used: int
    from_cache: bool = False
    description: str | None = None
    servings: int = 4
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None


class _TokenPool:
    """Round-robin pool of Groq API keys, each guarded by an asyncio.Semaphore."""

    def __init__(self, keys: list[str], concurrency: int) -> None:
        if not keys:
            raise ValueError("GROQ_API_KEYS is empty — set at least one key")
        self._slots = [(key, asyncio.Semaphore(concurrency)) for key in keys]
        self._index = 0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            key, sem = self._slots[self._index % len(self._slots)]
            self._index += 1
        async with sem:
            yield key

    def __len__(self) -> int:
        return len(self._slots)


# Module-level pool (built lazily so asyncio loop is ready)
_pool: _TokenPool | None = None


def _get_pool() -> _TokenPool:
    global _pool
    if _pool is None:
        raw = settings.GROQ_API_KEYS.strip()
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys and settings.GROQ_API_KEY:
            keys = [settings.GROQ_API_KEY]
        _pool = _TokenPool(keys, settings.GROQ_CONCURRENCY_PER_KEY)
        logger.info("Groq token pool initialised with %d key(s)", len(_pool))
    return _pool


_SYSTEM_PROMPT = (
    "Tu analyses le texte d'un post de réseau social pour en extraire une recette de cuisine. "
    "Retourne UNIQUEMENT un objet JSON valide avec exactement ces champs : "
    '{"title": string, "description": string ou null, "instructions": string, '
    '"servings": integer, "prep_time_minutes": integer ou null, '
    '"cook_time_minutes": integer ou null, '
    '"ingredients": [{"name": string, "quantity": float, "unit": string}]}. '
    "Ne retourne rien d'autre que le JSON."
)


class GroqRecipeExtractor:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self, api_key: str):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(
            base_url="https://api.groq.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        ) as client:
            yield client

    async def extract(self, text: str) -> ExtractedRecipe:
        """Extract a recipe from raw text. Returns cached result when available."""
        cache_key = f"groq:recipe:{hashlib.sha256(text.encode()).hexdigest()}"

        cached = await _get_redis().get(cache_key)
        if cached:
            logger.debug("Groq cache hit for key %s", cache_key[-8:])
            data = json.loads(cached)
            data["from_cache"] = True
            return ExtractedRecipe(**data)

        async with _get_pool().acquire() as api_key:
            extracted = await self._call_groq(text, api_key)

        cacheable = {k: v for k, v in asdict(extracted).items() if k != "from_cache"}
        await _get_redis().setex(
            cache_key, settings.GROQ_CACHE_TTL, json.dumps(cacheable)
        )
        logger.debug("Groq result cached under key %s", cache_key[-8:])

        return extracted

    async def _call_groq(self, text: str, api_key: str) -> ExtractedRecipe:
        async with self._client(api_key) as client:
            resp = await client.post(
                "/openai/v1/chat/completions",
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()

        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            stripped = "\n".join(lines[1:end])

        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Groq a retourné un JSON invalide : {content}") from exc

        ingredients = []
        for item in raw.get("ingredients", []):
            try:
                ingredients.append(
                    {
                        "name": str(item["name"]).strip(),
                        "quantity": float(item.get("quantity") or 1.0),
                        "unit": str(item.get("unit") or "pièce").strip().lower(),
                    }
                )
            except (KeyError, ValueError, TypeError):
                continue

        return ExtractedRecipe(
            title=str(raw.get("title", "")).strip() or "Recette importée",
            description=raw.get("description"),
            instructions=str(raw.get("instructions", "")).strip(),
            servings=int(raw.get("servings") or 4),
            prep_time_minutes=raw.get("prep_time_minutes"),
            cook_time_minutes=raw.get("cook_time_minutes"),
            ingredients=ingredients,
            tokens_used=tokens_used,
        )
