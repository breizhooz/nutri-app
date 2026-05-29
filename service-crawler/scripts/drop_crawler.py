"""
Purge des données de crawling et des recettes en attente.

Supprime toutes les lignes des tables :
  - crawl_result_users  (recettes en attente / validées / rejetées par user)
  - crawl_results       (contenus crawlés)
  - crawl_sources       (sources de crawl configurées)

Usage : python -m scripts.drop_crawler [--yes]

  --yes / -y : ne demande pas de confirmation (utile en CI / scripts).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _confirm(skip: bool) -> bool:
    if skip:
        return True
    answer = input(
        "Cette opération supprime TOUTES les sources de crawl, les résultats "
        "crawlés et les recettes en attente. Confirmer ? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes", "o", "oui"}


async def _drop_db() -> tuple[int, int, int]:
    from sqlalchemy import delete, func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models.crawl_result import CrawlResult
    from app.models.crawl_result_user import CrawlResultUser
    from app.models.crawl_source import CrawlSource

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            result_users = await session.scalar(
                select(func.count()).select_from(CrawlResultUser)
            )
            results = await session.scalar(
                select(func.count()).select_from(CrawlResult)
            )
            sources = await session.scalar(
                select(func.count()).select_from(CrawlSource)
            )

            # Ordre de suppression : liaisons user d'abord, puis résultats,
            # puis sources.
            await session.execute(delete(CrawlResultUser))
            await session.execute(delete(CrawlResult))
            await session.execute(delete(CrawlSource))
            await session.commit()
        return sources, results, result_users
    finally:
        await engine.dispose()


async def _run(skip_confirm: bool) -> None:
    if not _confirm(skip_confirm):
        print("Annulé.")
        return

    sources, results, result_users = await _drop_db()
    print(
        f"DB purgée : {sources} source(s), {results} résultat(s) crawlé(s), "
        f"{result_users} recette(s) en attente supprimée(s)."
    )


if __name__ == "__main__":
    skip = any(arg in {"--yes", "-y"} for arg in sys.argv[1:])
    asyncio.run(_run(skip))
