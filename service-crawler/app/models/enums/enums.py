from enum import Enum as PyEnum

class CrawlType(str, PyEnum):
    WEB = "web"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"

class CrawlStatus(str, PyEnum):
    WAITING = "waiting"
    VALID = "valid"
    REJECTED = "rejected"

class PushChannel(str, PyEnum):
    """Canal de livraison des notifications push."""
    WEB_PUSH = "web_push"  # VAPID / Service Worker navigateur
    EXPO = "expo"          # Expo Push Notifications (iOS + Android)