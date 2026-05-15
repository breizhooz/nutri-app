from enum import Enum as PyEnum

class CrawlType(str, PyEnum):
    WEB = "enums.crawl_type.web"
    INSTAGRAM = "enums.crawl_type.instagram"
    YOUTUBE = "enums.crawl_type.youtube"

class CrawStatus(str, PyEnum):
    WAITTING = "enums.crawl_status.waitting"
    VALID =  "enums.crawl_status.valid"
    REJECTED =  "enums.crawl_status.rejected"

