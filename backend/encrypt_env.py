"""CLI tool to encrypt backend/.env into backend/.env.enc."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

if __package__:
    from .secure_env import EncryptedEnvError, encrypt_env_text
else:  # pragma: no cover - allows `python backend/encrypt_env.py`
    from secure_env import EncryptedEnvError, encrypt_env_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt backend/.env using AES-GCM.")
    parser.add_argument(
        "-i",
        "--input",
        default=".env",
        help="Plaintext env file relative to backend/ (default: .env)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".env.enc",
        help="Destination encrypted file relative to backend/ (default: .env.enc)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    input_path = root / args.input
    output_path = root / args.output

    if not input_path.exists():
        raise EncryptedEnvError(f"Plaintext env file {input_path} does not exist.")
    if output_path.exists() and not args.force:
        raise EncryptedEnvError(
            f"{output_path} already exists. Use --force to overwrite the file."
        )

    env_text = input_path.read_text(encoding="utf-8")
    password = _prompt_password()
    encrypted = encrypt_env_text(env_text, password)
    output_path.write_text(encrypted, encoding="utf-8")
    print(f"Encrypted env saved to {output_path}.")
    print("Store or remove the plaintext env file securely; it is no longer needed at runtime.")


def _prompt_password() -> str:
    first = getpass.getpass("Create password for encrypted .env: ").strip()
    confirm = getpass.getpass("Confirm password: ").strip()
    if not first:
        raise EncryptedEnvError("Password cannot be empty.")
    if first != confirm:
        raise EncryptedEnvError("Passwords did not match.")
    return first


if __name__ == "__main__":
    main()
