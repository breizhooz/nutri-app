from enum import Enum as PyEnum

class CrawlType(str, PyEnum):
    WEB = "web"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"

class CrawlStatus(str, PyEnum):
    WAITING = "waiting"
    VALID = "valid"
    REJECTED = "rejected"
