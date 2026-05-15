class RecipeMapper:
    """Transforme un CrawlResult validé en payload recette pour service-recipe. Implémenté en Phase 5."""

    async def map(self, crawl_result) -> dict:
        raise NotImplementedError