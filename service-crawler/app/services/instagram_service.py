class InstagramService:
    """Extraction de posts Instagram via Instaloader. Implémenté en Phase 6."""

    async def fetch_posts(self, account: str) -> list[dict]:
        raise NotImplementedError