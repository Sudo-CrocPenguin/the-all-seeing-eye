from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.shared.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def build_session_factory(settings: Settings):
    return sessionmaker(bind=build_engine(settings), autoflush=False, autocommit=False)

