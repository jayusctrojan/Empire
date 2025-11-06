"""
Empire v7.3 - Encryption Service Tests
Tests for AES-256-GCM encryption functionality
"""

import pytest
from io import BytesIO
import base64

from app.services.encryption import EncryptionService


class TestEncryptionService:
    """Test suite for EncryptionService"""

    def test_encryption_service_initialization(self, encryption_service):
        """Test encryption service initializes correctly"""
        assert encryption_service.enabled is True
        assert encryption_service.KEY_SIZE == 32
        assert encryption_service.SALT_SIZE == 32
        assert encryption_service.NONCE_SIZE == 16
        assert encryption_service.TAG_SIZE == 16
        assert encryption_service.PBKDF2_ITERATIONS == 100000

    def test_encryption_service_disabled(self):
        """Test encryption service can be disabled"""
        service = EncryptionService(enabled=False)
        assert service.enabled is False

        with pytest.raises(ValueError, match="Encryption is disabled"):
            service.encrypt_file(BytesIO(b"test"), "password")

    def test_derive_key_from_password(self, encryption_service, sample_password):
        """Test key derivation from password"""
        salt = b"x" * 32  # 32-byte salt
        key = encryption_service.derive_key_from_password(sample_password, salt)

        assert len(key) == 32  # 256 bits
        assert isinstance(key, bytes)

    def test_key_derivation_consistency(self, encryption_service, sample_password):
        """Test that same password and salt produce same key"""
        salt = b"x" * 32
        key1 = encryption_service.derive_key_from_password(sample_password, salt)
        key2 = encryption_service.derive_key_from_password(sample_password, salt)

        assert key1 == key2

    def test_key_derivation_different_salts(self, encryption_service, sample_password):
        """Test that different salts produce different keys"""
        salt1 = b"a" * 32
        salt2 = b"b" * 32

        key1 = encryption_service.derive_key_from_password(sample_password, salt1)
        key2 = encryption_service.derive_key_from_password(sample_password, salt2)

        assert key1 != key2

    def test_encrypt_file_with_password(self, encryption_service, sample_file_data, sample_password):
        """Test file encryption with password"""
        encrypted_data, metadata = encryption_service.encrypt_file(
            sample_file_data,
            sample_password
        )

        # Check encrypted data
        assert isinstance(encrypted_data, BytesIO)
        encrypted_bytes = encrypted_data.read()
        assert len(encrypted_bytes) > 0

        # Check metadata
        assert metadata["algorithm"] == "AES-256-GCM"
        assert metadata["encrypted"] is True
        assert "salt" in metadata
        assert "nonce" in metadata
        assert "tag" in metadata

        # Verify metadata values are base64
        base64.b64decode(metadata["salt"])
        base64.b64decode(metadata["nonce"])
        base64.b64decode(metadata["tag"])

    def test_encrypt_decrypt_round_trip(self, encryption_service, sample_password):
        """Test encryption and decryption produces original data"""
        original_data = b"This is test data for encryption and decryption."
        file_data = BytesIO(original_data)

        # Encrypt
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Decrypt
        decrypted_data = encryption_service.decrypt_file(
            encrypted_data,
            sample_password,
            metadata
        )

        # Verify
        decrypted_bytes = decrypted_data.read()
        assert decrypted_bytes == original_data

    def test_decrypt_with_embedded_metadata(self, encryption_service, sample_password):
        """Test decryption using embedded metadata in file"""
        original_data = b"Test data for embedded metadata decryption."
        file_data = BytesIO(original_data)

        # Encrypt
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Decrypt without passing metadata (uses embedded)
        decrypted_data = encryption_service.decrypt_file(encrypted_data, sample_password)

        # Verify
        assert decrypted_data.read() == original_data

    def test_decrypt_with_wrong_password(self, encryption_service, sample_password):
        """Test decryption fails with wrong password"""
        file_data = BytesIO(b"Secret data")

        # Encrypt with correct password
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Try to decrypt with wrong password
        wrong_password = "wrong_password"

        with pytest.raises(ValueError, match="Decryption failed"):
            encryption_service.decrypt_file(encrypted_data, wrong_password, metadata)

    def test_decrypt_with_corrupted_data(self, encryption_service, sample_password):
        """Test decryption fails with corrupted ciphertext"""
        file_data = BytesIO(b"Test data")

        # Encrypt
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Corrupt the ciphertext
        encrypted_bytes = encrypted_data.read()
        corrupted_bytes = bytearray(encrypted_bytes)
        corrupted_bytes[50] ^= 0xFF  # Flip bits in the middle
        corrupted_data = BytesIO(bytes(corrupted_bytes))

        # Try to decrypt corrupted data
        with pytest.raises(ValueError, match="Decryption failed"):
            encryption_service.decrypt_file(corrupted_data, sample_password, metadata)

    def test_encrypt_with_raw_key(self, encryption_service):
        """Test encryption with raw 256-bit key"""
        key = encryption_service.generate_key()
        file_data = BytesIO(b"Test data for raw key encryption")

        encrypted_data, metadata = encryption_service.encrypt_file_with_key(file_data, key)

        # Verify metadata
        assert metadata["algorithm"] == "AES-256-GCM"
        assert metadata["encrypted"] is True
        assert metadata["key_derived"] is False
        assert "nonce" in metadata
        assert "tag" in metadata
        assert "salt" not in metadata  # No salt for raw key

    def test_encrypt_with_invalid_key_size(self, encryption_service):
        """Test encryption fails with invalid key size"""
        invalid_key = b"x" * 16  # 128 bits instead of 256
        file_data = BytesIO(b"Test data")

        with pytest.raises(ValueError, match="Key must be 32 bytes"):
            encryption_service.encrypt_file_with_key(file_data, invalid_key)

    def test_generate_key(self, encryption_service):
        """Test key generation produces valid 256-bit keys"""
        key = encryption_service.generate_key()

        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits

    def test_generate_key_uniqueness(self, encryption_service):
        """Test generated keys are unique"""
        key1 = encryption_service.generate_key()
        key2 = encryption_service.generate_key()

        assert key1 != key2

    def test_key_to_base64_conversion(self, encryption_service):
        """Test key to base64 conversion"""
        key = encryption_service.generate_key()
        key_str = encryption_service.key_to_base64(key)

        assert isinstance(key_str, str)
        # Verify it's valid base64
        decoded = base64.b64decode(key_str)
        assert decoded == key

    def test_key_from_base64_conversion(self, encryption_service):
        """Test base64 to key conversion"""
        key = encryption_service.generate_key()
        key_str = encryption_service.key_to_base64(key)
        restored_key = encryption_service.key_from_base64(key_str)

        assert restored_key == key

    def test_large_file_encryption(self, encryption_service, sample_password):
        """Test encryption of larger file (1MB)"""
        large_data = b"x" * (1024 * 1024)  # 1 MB
        file_data = BytesIO(large_data)

        # Encrypt
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Decrypt
        decrypted_data = encryption_service.decrypt_file(
            encrypted_data,
            sample_password,
            metadata
        )

        # Verify
        assert decrypted_data.read() == large_data

    def test_empty_file_encryption(self, encryption_service, sample_password):
        """Test encryption of empty file"""
        empty_data = b""
        file_data = BytesIO(empty_data)

        # Encrypt
        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Decrypt
        decrypted_data = encryption_service.decrypt_file(
            encrypted_data,
            sample_password,
            metadata
        )

        # Verify
        assert decrypted_data.read() == empty_data

    def test_encryption_metadata_format(self, encryption_service, sample_password):
        """Test metadata contains all required fields"""
        file_data = BytesIO(b"Test data")

        encrypted_data, metadata = encryption_service.encrypt_file(file_data, sample_password)

        # Check all required fields
        required_fields = ["salt", "nonce", "tag", "algorithm", "encrypted"]
        for field in required_fields:
            assert field in metadata

        # Check values
        assert len(base64.b64decode(metadata["salt"])) == 32
        assert len(base64.b64decode(metadata["nonce"])) == 16
        assert len(base64.b64decode(metadata["tag"])) == 16
        assert metadata["algorithm"] == "AES-256-GCM"
        assert metadata["encrypted"] is True
