"""
Database preparation at startup.

- Brand-new empty database: build the schema with Alembic, then (development
  only) seed demo data.
- Existing database: never altered here. If it is behind the latest migration
  the app refuses to start and says which command to run, so schema changes to
  real data are always a deliberate, backed-up step.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from . import config
from .database import SessionLocal, engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def current_revision():
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def prepare_database() -> None:
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    if not tables:
        print("Empty database - creating schema with Alembic...")
        command.upgrade(alembic_config(), "head")
    else:
        current, head = current_revision(), head_revision()
        if current is None:
            raise RuntimeError(
                "This database has tables but no Alembic revision. If it is the original "
                "CampusOne database run:  alembic stamp 0001  then  alembic upgrade head")
        if current != head:
            raise RuntimeError(
                f"Database schema is at revision {current} but the code needs {head}. "
                "Back up the database, then run:  alembic upgrade head")

    from . import models
    with SessionLocal() as db:
        users = db.query(models.User).count()
    if users:
        print(f"Database ready ({users} users, schema revision {current_revision()}).")
        return
    if not config.AUTO_SEED:
        print("Database has no users and AUTO_SEED is off - starting with an empty database.")
        return
    print("No users found in the database - running seed script...")
    from . import seed
    try:
        seed.run()
    except Exception as exc:
        print(f"SEED FAILED: {exc}")
        print("Login will not work until this is fixed. Common cause: bcrypt/passlib "
              "version mismatch - run 'pip install bcrypt==4.0.1' and restart.")
        raise
