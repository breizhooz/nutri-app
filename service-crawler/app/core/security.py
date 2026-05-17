from jose import jwt
from app.core.config import settings


def decode_token(token: str) -> dict:
    """Décode et vérifie la signature du token JWT."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
