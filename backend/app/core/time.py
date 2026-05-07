from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """
    Return a naive datetime representing the current UTC instant.

    We keep it naive on purpose to preserve compatibility with the current
    database schema and payload behavior, while avoiding datetime.utcnow().
    """
    return datetime.now(UTC).replace(tzinfo=None)