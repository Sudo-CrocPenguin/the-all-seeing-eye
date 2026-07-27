from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.shared.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    if settings.database_url.startswith("sqlite"):
        connect_args: dict[str, object] = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            return create_engine(
                settings.database_url,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(settings.database_url, connect_args=connect_args)

    return create_engine(settings.database_url, pool_pre_ping=True)


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=build_engine(settings), autoflush=False, autocommit=False)


def import_database_models() -> None:
    import_module("backend.app.audit.infrastructure.sqlalchemy_models")
    import_module("backend.app.devices.infrastructure.sqlalchemy_models")


def create_database_schema(engine: Engine) -> None:
    import_database_models()
    Base.metadata.create_all(bind=engine)
