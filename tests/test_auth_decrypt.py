import base64

from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from discord_cli.auth.decrypt import decrypt_token, ENCRYPTED_PREFIX


def _encrypt_with_v10(plaintext: str, password: str, iterations: int) -> str:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=iterations,
    )
    key = kdf.derive(password.encode())
    iv = b" " * 16

    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode()) + padder.finalize()

    cipher = Cipher(algorithms.AES128(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    blob = b"v10" + ciphertext
    return ENCRYPTED_PREFIX + base64.b64encode(blob).decode()


def test_decrypt_token_handles_plaintext() -> None:
    assert (
        decrypt_token("plain-token-123", password="x", iterations=1)
        == "plain-token-123"
    )


def test_decrypt_token_decrypts_v10_encrypted() -> None:
    password = "test-password"
    original = "ODUyODkyMjk3NjYx.GX5Xdp.22jsdSqEiHLU"
    encrypted = _encrypt_with_v10(original, password, iterations=1)

    result = decrypt_token(encrypted, password=password, iterations=1)
    assert result == original


def test_decrypt_token_strips_quotes_from_decrypted_value() -> None:
    password = "test-password"
    encrypted = _encrypt_with_v10('"ODUyODky.GX5.token"', password, iterations=1)

    result = decrypt_token(encrypted, password=password, iterations=1)
    assert result == "ODUyODky.GX5.token"


def _encrypt_with_v10_gcm(plaintext: str, password: str, iterations: int) -> str:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=32,
        salt=b"saltysalt",
        iterations=iterations,
    )
    key = kdf.derive(password.encode())
    nonce = b"\x00" * 12

    cipher = Cipher(algorithms.AES256(key), modes.GCM(nonce))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
    tag = encryptor.tag

    blob = b"v10" + nonce + ciphertext + tag
    return ENCRYPTED_PREFIX + base64.b64encode(blob).decode()


def test_decrypt_token_decrypts_v10_gcm() -> None:
    password = "test-password"
    original = "gcm-secret-token"
    encrypted = _encrypt_with_v10_gcm(original, password, iterations=1)

    result = decrypt_token(encrypted, password=password, iterations=1)
    assert result == original


def test_decrypt_falls_through_to_gcm_when_cbc_produces_garbage() -> None:
    from unittest.mock import patch

    password = "test-password"
    original = "ODUy.GX5.real-token"
    encrypted = _encrypt_with_v10_gcm(original, password, iterations=1)

    with patch(
        "discord_cli.auth.decrypt._try_cbc",
        return_value="\x00\x01garbage-not-a-token\xff",
    ):
        result = decrypt_token(encrypted, password=password, iterations=1)

    assert result == original
