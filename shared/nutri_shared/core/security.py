import os

import jwt


def decode_token(token: str) -> dict:
    secret = os.environ["JWT_SECRET"]
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    return jwt.decode(token, secret, algorithms=[algorithm])
