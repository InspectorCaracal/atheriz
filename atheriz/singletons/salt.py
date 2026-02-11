import secrets
from atheriz import settings
from pathlib import Path

_SALT: str | None = None


def get_salt() -> str:
    """
    Get the global salt value.
    If save/salt.txt exists, cache and return that value.
    Otherwise generate a random 64-bit number, write it to salt.txt, cache and return.
    """
    global _SALT
    if _SALT is not None:
        return _SALT

    salt_file = Path(settings.SECRET_PATH) / "salt.txt"

    if salt_file.exists():
        _SALT = salt_file.read_text().strip()
        return _SALT

    salt_val = str(secrets.randbits(64))
    salt_file.parent.mkdir(parents=True, exist_ok=True)
    salt_file.write_text(salt_val)
    _SALT = salt_val
    return _SALT
