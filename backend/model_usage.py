"""Reserve provider calls atomically per signed-in account and UTC day."""

from datetime import datetime, time, timedelta, timezone
from math import ceil

from fastapi import HTTPException

from .db import connect

DAILY_MODEL_CALL_LIMIT = 15


def reserve_model_calls(user_id: int, calls: int) -> None:
    if calls > DAILY_MODEL_CALL_LIMIT:
        raise HTTPException(
            413, "This PDF needs more than the daily model call limit. Split it into smaller PDFs."
        )

    now = datetime.now(timezone.utc)
    today = now.date()
    with connect() as connection:
        reservation = connection.execute(
            """
            INSERT INTO daily_model_usage (user_id, usage_day, calls)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, usage_day) DO UPDATE
            SET calls = daily_model_usage.calls + EXCLUDED.calls
            WHERE daily_model_usage.calls + EXCLUDED.calls <= %s
            RETURNING calls
            """,
            (user_id, today, calls, DAILY_MODEL_CALL_LIMIT),
        ).fetchone()

    if reservation is None:
        tomorrow = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)
        retry_after = ceil((tomorrow - now).total_seconds())
        raise HTTPException(
            429,
            f"This account has reached its daily limit of {DAILY_MODEL_CALL_LIMIT} model calls "
            "or has too few left for this request. The limit resets at midnight UTC.",
            headers={"Retry-After": str(retry_after)},
        )
