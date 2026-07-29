from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def to_iso(value: datetime) -> str:
    return value.isoformat()

