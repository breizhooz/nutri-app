from fastapi import HTTPException


class AppException(HTTPException):
    """Base exception that produces a structured {"error": {"code": ..., "message": ...}} response."""

    def __init__(self, status_code: int, code: str, message: str):
        self.code = code
        super().__init__(status_code=status_code, detail=message)