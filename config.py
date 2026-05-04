"""
Configuration loader — reads from environment variables or a local .env file.

Copy .env.example to .env and fill in your credentials. Never commit .env.
"""

import os
from pathlib import Path

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required env var '{key}' is not set. "
            "Add it to your .env file or export it before running."
        )
    return val
