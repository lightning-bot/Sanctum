from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, validator

from ..errors import NotFound

router = APIRouter()


class TimerPayload(BaseModel):
    event: str
    created: datetime
    expiry: Optional[datetime]
    extra: Optional[dict]

    @validator('created', 'expiry')
    def dt_validator(cls, value):
        return value.replace(tzinfo=None)


class Timer(BaseModel):
    id: int
    event: str
    created: datetime
    expiry: Optional[datetime]
    extra: Optional[dict]

    @validator('created', 'expiry', pre=True)
    def dt_validator(cls, value):
        return value.replace(tzinfo=timezone.utc)

    @classmethod
    def from_record(cls, record):
        return cls(**record)


@router.get("/timers", response_model=List[Timer])
async def get_timers(request: Request, limit: int = 1):
    query = """SELECT * FROM timers LIMIT $1;"""
    records = await request.app.pool.fetch(query, limit)
    return list(map(Timer.from_record, records))


@router.get("/timers/{id}", response_model=Timer)
async def get_timer(id: int, request: Request):
    query = """SELECT * FROM timers WHERE id=$1;"""
    record = await request.app.pool.fetchrow(query, id)
    if not record:
        raise HTTPException(404, f"Timer with id {id} was not found!")

    return Timer.from_record(record)


@router.put("/timers", response_model=Dict[str, int])
async def create_new_timer(payload: TimerPayload, request: Request):
    """Creates a new timer.
    Returns a json object with the id only."""
    if payload.extra:
        query = """INSERT INTO timers (event, created, expiry, extra)
                   VALUES ($1, $2, $3, $4::jsonb)
                   RETURNING id;"""
        args = [payload.event, payload.created, payload.expiry, payload.extra]
    else:
        query = """INSERT INTO timers (event, created, expiry)
                   VALUES ($1, $2, $3)
                   RETURNING id;"""
        args = [payload.event, payload.created, payload.expiry]

    _id = await request.app.pool.fetchval(query, *args)

    return {"id": _id}


@router.delete("/timers/{id}")
async def delete_timer(id: int, request: Request):
    query = """DELETE FROM timers WHERE id=$1;"""
    resp = await request.app.pool.execute(query, id)

    if resp.split()[1] == "0":
        raise HTTPException(404, "Timer with id {id} was not found!")


@router.get("/users/{user_id}/reminders", response_model=List[Timer])
async def get_user_reminders(user_id: int, request: Request, limit: int = 10):
    """
    Gets a users reminders.
    """
    qlimit = max(10, 25)
    query = """SELECT *
               FROM timers
               WHERE event = 'reminder'
               AND extra ->> 'author' = $1
               ORDER BY expiry
               LIMIT $2;
            """

    records = await request.app.pool.fetch(query, str(user_id), limit)

    if not records:
        raise NotFound(message=f"{user_id}'s reminders were not found!")

    return list(map(Timer.from_record, records))

@router.delete("/users/{user_id}/reminders/{reminder_id}")
async def delete_user_reminder(user_id: int, reminder_id: int, request: Request):
    """
    Deletes a user's reminder by ID.
    """
    query = """DELETE FROM timers
               WHERE id = $1
               AND event = 'reminder'
               AND extra ->> 'author' = $2;
            """
    result = await request.app.pool.execute(query, reminder_id, str(user_id))

    if result == "DELETE 0":
        raise NotFound(message=f"Unable to find a reminder belonging to {user_id} with ID {reminder_id}")

    return {}


@router.delete("/users/{user_id}/reminders")
async def bulk_delete_user_reminders(user_id: int, request: Request):
    """
    Bulk deletes all user reminders
    """
    query = """DELETE FROM timers
               WHERE event = 'reminder'
               AND extra ->> 'author' = $1
               RETURNING id;
            """
    records = await request.app.pool.fetch(query, str(user_id))
    ids = [r['id'] for r in records]
    return {"ids": ids}