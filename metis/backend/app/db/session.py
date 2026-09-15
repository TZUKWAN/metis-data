"""DB session management + init (P01-010). SQLite via SQLAlchemy; Repository layer is the only access path."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_ENGINE = None
_SESSION_FACTORY: sessionmaker | None = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        url = get_settings().db_url
        _ENGINE = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        if url.startswith("sqlite"):

            @event.listens_for(_ENGINE, "connect")
            def _fk_on(dbapi_conn, _):  # pragma: no cover
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()

    return _ENGINE


def get_session_factory() -> sessionmaker:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SESSION_FACTORY


def init_db() -> None:
    from app.db.models import Base

    get_settings().ensure_dirs()
    _migrate_conversation_tables()
    Base.metadata.create_all(get_engine())


def _migrate_conversation_tables() -> None:
    """Dev-safe schema drift: add columns introduced after a table already exists.

    create_all never alters existing tables; conversation_* tables evolved across
    the conversational-redesign rounds, so missing columns are added via ALTER TABLE.
    """
    from sqlalchemy import text

    from app.ui import models as ui_models

    engine = get_engine()
    with engine.connect() as conn:
        for table in (
            ui_models.ConversationRow,
            ui_models.ConversationMessageRow,
            ui_models.ConversationTaskRow,
            ui_models.ConversationResultLinkRow,
            ui_models.ConversationInterventionRow,
        ):
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table.__tablename__})"))}
            if not existing:
                continue
            for col in table.__table__.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    conn.execute(text(f"ALTER TABLE {table.__tablename__} ADD COLUMN {col.name} {col_type}"))
        conn.commit()


def new_session() -> Session:
    return get_session_factory()()


def reset_engine() -> None:
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None
