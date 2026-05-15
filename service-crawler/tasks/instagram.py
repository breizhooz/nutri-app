from celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def crawl_instagram(self, source_id: str, account: str):
    """Crawl un compte Instagram et stocke les nouveaux posts EN_ATTENTE. Implémenté en Phase 6."""
    raise NotImplementedError