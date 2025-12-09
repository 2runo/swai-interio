"""Helpers for encrypting and decrypting the backend environment file."""

from __future__ import annotations

import ast
import base64
import getpass
import logging
import os
from pathlib import Path
from typing import Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_PREFIX = "ENCV1:"
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KEY_SIZE = 32

logger = logging.getLogger(__name__)
_ENV_LOADED = False


class EncryptedEnvError(RuntimeError):
    """Raised when encrypted environment operations fail."""


def ensure_encrypted_env(encrypted_filename: str = ".env.enc") -> None:
    """Prompt for the password (if needed) and load env vars from encrypted file."""
    global _ENV_LOADED
    if _ENV_LOADED or os.environ.get("BACKEND_ENV_DECRYPTED") == "1":
        return

    encrypted_path = Path(__file__).with_name(encrypted_filename)
    if not encrypted_path.exists():
        raise EncryptedEnvError(
            f"Encrypted env file {encrypted_path} not found. "
            "Create it with backend/encrypt_env.py before starting the server."
        )

    password = os.environ.get("BACKEND_ENV_PASSWORD")
    if not password:
        password = _prompt_for_password(encrypted_path)

    try:
        env_text = decrypt_env_file(encrypted_path, password)
    except Exception as error:
        print("비밀번호가 잘못되었습니다.")
        raise Exception("비밀번호가 잘못되었습니다.")

    env_values = parse_env(env_text)
    for key, value in env_values.items():
        if key not in os.environ:
            os.environ[key] = value

    os.environ["BACKEND_ENV_DECRYPTED"] = "1"
    _ENV_LOADED = True


def encrypt_env_text(env_text: str, password: str) -> str:
    """Return encrypted text that can be safely written to disk."""
    if not password:
        raise ValueError("Password is required for encryption.")
    plaintext = env_text.encode("utf-8")
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key = _derive_key(password, salt)
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    payload = salt + nonce + ciphertext
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    return f"{_PREFIX}{encoded}"


def decrypt_env_file(path: Path, password: str) -> str:
    """Decrypt an encrypted env file and return its plaintext contents."""
    raw = path.read_text(encoding="utf-8").strip()
    plaintext = decrypt_env_text(raw, password)
    return plaintext.decode("utf-8")


def decrypt_env_text(raw_text: str, password: str) -> bytes:
    """Decrypt raw text that was produced by encrypt_env_text."""
    if not raw_text.startswith(_PREFIX):
        raise ValueError("Unsupported encrypted env format.")
    encoded = raw_text[len(_PREFIX) :].strip()
    payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
    if len(payload) <= _SALT_SIZE + _NONCE_SIZE:
        raise ValueError("Encrypted payload too short.")

    salt = payload[:_SALT_SIZE]
    nonce = payload[_SALT_SIZE : _SALT_SIZE + _NONCE_SIZE]
    ciphertext = payload[_SALT_SIZE + _NONCE_SIZE :]
    key = _derive_key(password, salt)
    cipher = AESGCM(key)
    return cipher.decrypt(nonce, ciphertext, None)


def parse_env(env_text: str) -> Dict[str, str]:
    """Parse dotenv-style key=value pairs from plaintext."""
    env: Dict[str, str] = {}
    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = raw_value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = _unquote(value)
        env[key] = value
    return env


def _prompt_for_password(path: Path) -> str:
    try:
        return getpass.getpass(f"Password to decrypt {path.name} (전달받은 비밀번호를 입력하세요): ").strip()
    except (EOFError, KeyboardInterrupt) as error:  # pragma: no cover - interactive only
        raise EncryptedEnvError("Password prompt aborted.") from error


def _derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise ValueError("Password is empty.")
    kdf = Scrypt(
        salt=salt,
        length=_KEY_SIZE,
        n=2**15,
        r=8,
        p=1,
    )
    return kdf.derive(password.encode("utf-8"))


def _unquote(value: str) -> str:
    try:
        return ast.literal_eval(value)
    except Exception:
        return value[1:-1]


__all__ = [
    "EncryptedEnvError",
    "ensure_encrypted_env",
    "encrypt_env_text",
    "decrypt_env_file",
    "decrypt_env_text",
    "parse_env",
]
