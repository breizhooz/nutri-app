from celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_url(self, source_id: str, url: str):
    """Crawl une URL web et stocke un CrawlResult EN_ATTENTE. Implémenté en Phase 3."""
    raise NotImplementedError