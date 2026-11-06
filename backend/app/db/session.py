"""
NewGenHealthAI — db/session.py
SQLAlchemy engine and session factory.
"""

import datetime
import os
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import CHAT_DB_PATH
from app.core.logging_config import logger


# Register explicit adapters for datetime.datetime and datetime.date to eliminate
# Python 3.12+ DeprecationWarning for the default sqlite3 adapter, preserving legacy
# ISO format with space separation (e.g. 'YYYY-MM-DD HH:MM:SS.mmmmmm') and UTC offsets.
def _adapt_datetime_iso(val: datetime.datetime) -> str:
    """Explicit ISO adapter matching legacy sqlite3 default adapter format."""
    return val.isoformat(" ")


def _adapt_date_iso(val: datetime.date) -> str:
    """Explicit ISO adapter for date objects."""
    return val.isoformat()


sqlite3.register_adapter(datetime.datetime, _adapt_datetime_iso)
sqlite3.register_adapter(datetime.date, _adapt_date_iso)


def get_engine(db_path: str = CHAT_DB_PATH):
    """Create and return a SQLAlchemy engine for the given SQLite path."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    logger.debug("Database engine created at %s", db_path)
    return create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )


def get_session_factory(engine):
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Module-level singletons
engine = get_engine()
SessionLocal = get_session_factory(engine)
