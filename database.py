# ============================================================
# database.py — SQLAlchemy engine & session factory
# Supports SQLite (default) and PostgreSQL
# ============================================================

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _get_engine(database_url: str):
    """
    Create the SQLAlchemy engine.
    SQLite gets special flags for thread safety with async code.
    """
    if database_url.startswith("sqlite"):
        # Ensure the data/ directory exists
        db_path = database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        # Enable WAL mode for better concurrency on SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL or other RDBMS
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )

    return engine


def init_db(database_url: str):
    """
    Initialise the database:
    - Create engine
    - Create all tables (if they don't exist)
    - Return SessionLocal factory
    """
    from models.user import User          # noqa: F401 — import triggers table registration
    from models.checkin import CheckinLog  # noqa: F401
    from models.referral import Referral   # noqa: F401
    from models.task import UserTask        # noqa: F401

    engine = _get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised: %s", database_url)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, SessionLocal
