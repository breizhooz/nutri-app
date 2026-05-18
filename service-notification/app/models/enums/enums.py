from enum import Enum as PyEnum


class NotificationType(str, PyEnum):
    MACRO_ERROR = "macro_error"
    CRAWL_DONE = "crawl_done"
    SYSTEM = "system"


class NotificationStatus(str, PyEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"