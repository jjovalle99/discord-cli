import base64

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENCRYPTED_PREFIX = "dQw4w9WgXcQ:"


def is_encrypted(raw: str) -> bool:
    return raw.startswith(ENCRYPTED_PREFIX)


V10_PREFIX = b"v10"
SALT = b"saltysalt"
IV = b" " * 16
CBC_KEY_LENGTH = 16
GCM_KEY_LENGTH = 32
GCM_NONCE_LENGTH = 12
GCM_TAG_LENGTH = 16


def _derive_key(password: str, iterations: int, length: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=length,
        salt=SALT,
        iterations=iterations,
    )
    return kdf.derive(password.encode())


def _try_cbc(ciphertext: bytes, key: bytes) -> str:
    cipher = Cipher(algorithms.AES128(key), modes.CBC(IV))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode()


def _try_gcm(payload: bytes, key: bytes) -> str:
    nonce = payload[:GCM_NONCE_LENGTH]
    ciphertext = payload[GCM_NONCE_LENGTH:-GCM_TAG_LENGTH]
    tag = payload[-GCM_TAG_LENGTH:]

    cipher = Cipher(algorithms.AES256(key), modes.GCM(nonce, tag))
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext.decode()


def _looks_like_token(value: str) -> bool:
    stripped = value.strip('"')
    return (
        len(stripped) >= 10
        and "." in stripped
        and stripped.isascii()
        and all(c.isprintable() for c in stripped)
    )


def decrypt_token(raw: str, *, password: str, iterations: int) -> str:
    if not raw.startswith(ENCRYPTED_PREFIX):
        return raw

    encoded = raw[len(ENCRYPTED_PREFIX) :]
    blob = base64.b64decode(encoded)

    if not blob.startswith(V10_PREFIX):
        msg = f"Unknown encryption version: {blob[:3]!r}"
        raise ValueError(msg)

    payload = blob[len(V10_PREFIX) :]

    try:
        cbc_key = _derive_key(password, iterations, CBC_KEY_LENGTH)
        result = _try_cbc(payload, cbc_key)
        if not _looks_like_token(result):
            raise ValueError("CBC output doesn't look like a Discord token")
    except (ValueError, UnicodeDecodeError):
        gcm_key = _derive_key(password, iterations, GCM_KEY_LENGTH)
        result = _try_gcm(payload, gcm_key)

    return result.strip('"')
