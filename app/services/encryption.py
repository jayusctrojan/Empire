"""
Empire v7.3 - File Encryption Service
Zero-knowledge AES-256 encryption for sensitive files using PyCryptodome
"""

import os
import logging
from typing import Optional, Tuple, BinaryIO
from io import BytesIO
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
import base64

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Zero-knowledge file encryption using AES-256-GCM

    Features:
    - AES-256-GCM authenticated encryption
    - PBKDF2 key derivation from passwords
    - Per-file random salts and nonces
    - Authenticated encryption prevents tampering
    - Optional encryption (can be disabled)

    Security:
    - Keys never stored on server
    - Users responsible for key management
    - Each file gets unique salt and nonce
    - GCM mode provides authentication
    """

    # Encryption parameters
    KEY_SIZE = 32  # 256 bits
    SALT_SIZE = 32  # 256 bits
    NONCE_SIZE = 16  # 128 bits for GCM
    TAG_SIZE = 16  # 128 bits authentication tag
    PBKDF2_ITERATIONS = 100000  # Recommended by NIST

    def __init__(self, enabled: bool = True):
        """
        Initialize encryption service

        Args:
            enabled: Whether encryption is enabled (default: True)
        """
        self.enabled = enabled
        if enabled:
            logger.info("Encryption service initialized (AES-256-GCM)")
        else:
            logger.warning("Encryption service disabled - files will be stored unencrypted")

    def derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2

        Args:
            password: User password
            salt: Random salt (32 bytes)

        Returns:
            Derived 256-bit key
        """
        key = PBKDF2(
            password,
            salt,
            dkLen=self.KEY_SIZE,
            count=self.PBKDF2_ITERATIONS,
            hmac_hash_module=SHA256
        )
        return key

    def encrypt_file(
        self,
        file_data: BinaryIO,
        password: str
    ) -> Tuple[BytesIO, dict]:
        """
        Encrypt file data using AES-256-GCM

        Args:
            file_data: File-like object containing plaintext data
            password: Encryption password

        Returns:
            Tuple of (encrypted_file_data, encryption_metadata)

        Encryption metadata contains:
            - salt: Base64-encoded salt for key derivation
            - nonce: Base64-encoded nonce for GCM mode
            - tag: Base64-encoded authentication tag
            - algorithm: "AES-256-GCM"

        File format:
            [salt (32 bytes)][nonce (16 bytes)][ciphertext][tag (16 bytes)]
        """
        if not self.enabled:
            raise ValueError("Encryption is disabled")

        logger.info("Encrypting file with AES-256-GCM")

        # Read plaintext data
        plaintext = file_data.read()

        # Generate random salt and nonce
        salt = get_random_bytes(self.SALT_SIZE)
        nonce = get_random_bytes(self.NONCE_SIZE)

        # Derive key from password
        key = self.derive_key_from_password(password, salt)

        # Create AES-GCM cipher
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

        # Encrypt and authenticate
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)

        # Create encrypted file with salt, nonce, ciphertext, and tag
        encrypted_data = BytesIO()
        encrypted_data.write(salt)
        encrypted_data.write(nonce)
        encrypted_data.write(ciphertext)
        encrypted_data.write(tag)
        encrypted_data.seek(0)

        # Create metadata for storage (needed for decryption)
        metadata = {
            "salt": base64.b64encode(salt).decode('utf-8'),
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8'),
            "algorithm": "AES-256-GCM",
            "encrypted": True
        }

        logger.info(
            f"File encrypted successfully - "
            f"plaintext: {len(plaintext)} bytes, ciphertext: {len(ciphertext)} bytes"
        )

        return encrypted_data, metadata

    def decrypt_file(
        self,
        encrypted_file_data: BinaryIO,
        password: str,
        metadata: Optional[dict] = None
    ) -> BytesIO:
        """
        Decrypt file data using AES-256-GCM

        Args:
            encrypted_file_data: File-like object containing encrypted data
            password: Decryption password
            metadata: Optional encryption metadata (if not embedded in file)

        Returns:
            Decrypted file data as BytesIO

        Raises:
            ValueError: If decryption fails or authentication fails
        """
        if not self.enabled:
            raise ValueError("Encryption is disabled")

        logger.info("Decrypting file with AES-256-GCM")

        # Read encrypted data
        encrypted_data = encrypted_file_data.read()

        # Extract salt, nonce, ciphertext, and tag
        # Note: File format is always [salt][nonce][ciphertext][tag]
        # Metadata is just for verification/alternate storage
        salt = encrypted_data[:self.SALT_SIZE]
        nonce = encrypted_data[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
        ciphertext = encrypted_data[self.SALT_SIZE + self.NONCE_SIZE:-self.TAG_SIZE]
        tag = encrypted_data[-self.TAG_SIZE:]

        # Derive key from password
        key = self.derive_key_from_password(password, salt)

        # Create AES-GCM cipher
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

        try:
            # Decrypt and verify authentication tag
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError as e:
            logger.error("Decryption failed - invalid password or corrupted data")
            raise ValueError("Decryption failed - invalid password or corrupted file") from e

        # Return decrypted data
        decrypted_data = BytesIO(plaintext)

        logger.info(f"File decrypted successfully - {len(plaintext)} bytes")

        return decrypted_data

    def encrypt_file_with_key(
        self,
        file_data: BinaryIO,
        key: bytes
    ) -> Tuple[BytesIO, dict]:
        """
        Encrypt file using raw key (not password-derived)

        Args:
            file_data: File-like object containing plaintext data
            key: 32-byte encryption key

        Returns:
            Tuple of (encrypted_file_data, encryption_metadata)
        """
        if not self.enabled:
            raise ValueError("Encryption is disabled")

        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")

        logger.info("Encrypting file with AES-256-GCM (raw key)")

        # Read plaintext data
        plaintext = file_data.read()

        # Generate random nonce
        nonce = get_random_bytes(self.NONCE_SIZE)

        # Create AES-GCM cipher
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

        # Encrypt and authenticate
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)

        # Create encrypted file with nonce, ciphertext, and tag
        encrypted_data = BytesIO()
        encrypted_data.write(nonce)
        encrypted_data.write(ciphertext)
        encrypted_data.write(tag)
        encrypted_data.seek(0)

        # Create metadata
        metadata = {
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8'),
            "algorithm": "AES-256-GCM",
            "encrypted": True,
            "key_derived": False
        }

        logger.info(f"File encrypted with raw key - {len(ciphertext)} bytes")

        return encrypted_data, metadata

    def generate_key(self) -> bytes:
        """
        Generate a random 256-bit encryption key

        Returns:
            32-byte random key
        """
        return get_random_bytes(self.KEY_SIZE)

    def key_to_base64(self, key: bytes) -> str:
        """
        Convert key to base64 string for storage/transmission

        Args:
            key: Raw key bytes

        Returns:
            Base64-encoded key
        """
        return base64.b64encode(key).decode('utf-8')

    def key_from_base64(self, key_str: str) -> bytes:
        """
        Convert base64 string back to key bytes

        Args:
            key_str: Base64-encoded key

        Returns:
            Raw key bytes
        """
        return base64.b64decode(key_str)


# Singleton instance
_encryption_service = None


def get_encryption_service(enabled: bool = True) -> EncryptionService:
    """
    Get or create encryption service singleton

    Args:
        enabled: Whether encryption is enabled

    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        # Check environment variable for encryption setting
        env_enabled = os.getenv("FILE_ENCRYPTION_ENABLED", "true").lower() == "true"
        _encryption_service = EncryptionService(enabled=enabled and env_enabled)
    return _encryption_service
