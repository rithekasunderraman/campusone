"""
Document storage abstraction.

Callers only ever use save / retrieve / delete by key. Which backend holds the
bytes is a configuration choice (STORAGE_BACKEND), so moving from the local
filesystem to another store is a config change rather than a rewrite.
"""
import re
import uuid
from pathlib import Path
from typing import Protocol

from . import config


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str = "") -> None: ...
    def retrieve(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _check_key(key: str) -> str:
    if not _SAFE_KEY.match(key) or ".." in key:
        raise StorageError(f"Unsafe storage key: {key!r}")
    return key


def new_key(prefix: str, filename: str) -> str:
    """A collision-free key that keeps only the file extension from user input."""
    ext = Path(filename or "").suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext or ""):
        ext = ""
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}{ext}"


class LocalStorage:
    """Files on the local filesystem under a single base directory."""

    def __init__(self, base_dir: Path):
        self.base = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self.base / _check_key(key)).resolve()
        if self.base not in path.parents:
            raise StorageError("Storage key escapes the storage directory.")
        return path

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def retrieve(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("Stored file not found.")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class DatabaseStorage:
    """Bytes kept in the application database (table stored_files).

    Suitable for hosts without a persistent disk: documents live in the managed
    database and survive redeploys with no extra service to configure.
    """

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        from . import models
        from .database import SessionLocal
        _check_key(key)
        with SessionLocal() as db:
            inst = db.query(models.Institution.id).order_by(models.Institution.id).first()
            db.merge(models.StoredFile(key=key, institution_id=inst[0], content=data, content_type=content_type))
            db.commit()

    def retrieve(self, key: str) -> bytes:
        from . import models
        from .database import SessionLocal
        with SessionLocal() as db:
            row = db.get(models.StoredFile, _check_key(key))
            if row is None:
                raise StorageError("Stored file not found.")
            return bytes(row.content)

    def delete(self, key: str) -> None:
        from . import models
        from .database import SessionLocal
        with SessionLocal() as db:
            row = db.get(models.StoredFile, _check_key(key))
            if row is not None:
                db.delete(row)
                db.commit()


def get_storage() -> Storage:
    if config.STORAGE_BACKEND == "database":
        return DatabaseStorage()
    if config.STORAGE_BACKEND == "local":
        return LocalStorage(config.STORAGE_DIR)
    raise StorageError(f"Unknown STORAGE_BACKEND: {config.STORAGE_BACKEND!r} (use 'local' or 'database').")
