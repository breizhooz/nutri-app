"""Fernet symmetric encryption utilities for sensitive stored fields."""

from cryptography.fernet import Fernet


class CryptoService:
    """Provides Fernet encrypt/decrypt static methods.

    All sensitive fields (TOTP secrets, OAuth tokens) stored in the DB
    must pass through this service.
    """

    @staticmethod
    def encrypt(value: str, key: str) -> str:
        """Encrypt a plain-text value with the given Fernet key.

        Args:
            value: The plain-text string to encrypt.
            key: A URL-safe base64-encoded 32-byte Fernet key.

        Returns:
            The encrypted value as a URL-safe base64 string.
        """
        return Fernet(key.encode()).encrypt(value.encode()).decode()

    @staticmethod
    def decrypt(value: str, key: str) -> str:
        """Decrypt a Fernet-encrypted value.

        Args:
            value: The encrypted string produced by encrypt().
            key: The same Fernet key used during encryption.

        Returns:
            The original plain-text string.

        Raises:
            cryptography.fernet.InvalidToken: If the token is tampered or key is wrong.
        """
        return Fernet(key.encode()).decrypt(value.encode()).decode()

    @staticmethod
    def generate_key() -> str:
        """Generate a fresh Fernet key suitable for use as MFA_TOTP_ENCRYPTION_KEY.

        Returns:
            A URL-safe base64-encoded 32-byte key string.
        """
        return Fernet.generate_key().decode()
