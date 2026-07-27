from collections.abc import AsyncIterator

from fastapi import Request

from backend.app.shared.container import AppContainer, RuntimeContainer


async def get_container(request: Request) -> AsyncIterator[AppContainer]:
    runtime_container: RuntimeContainer = request.app.state.container

    if runtime_container.settings.persistence_backend == "memory":
        yield runtime_container.build_memory_container()
        return

    if runtime_container.session_factory is None:
        raise RuntimeError("La persistencia SQLAlchemy no tiene session_factory configurado")

    with runtime_container.session_factory() as session:
        try:
            yield runtime_container.build_sqlalchemy_container(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
