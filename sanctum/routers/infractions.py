from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, validator

from ..errors import NotFound
from ..security import requires_api_key
from ..utils import build_update_query


class InfractionType(IntEnum):
    WARN = 1
    KICK = 2
    BAN = 3
    TIMEBAN = 4
    UNBAN = 5
    MUTE = 6
    UNMUTE = 7
    TIMEMUTE = 8
    TEMPROLE = 9


class Infraction(BaseModel):
    guild_id: int
    target_id: int
    moderator_id: int
    action: InfractionType
    reason: str
    created_at: datetime
    expiry: datetime
    active: bool
    extra: dict = {}

    @validator('created_at', pre=True)
    def dt_validator(cls, value):
        return value.replace(tzinfo=timezone.utc)


class PatchableInfraction(BaseModel):
    target_id: Optional[int]
    moderator_id: Optional[int]
    reason: Optional[str]
    active: Optional[bool]


def serialize_infraction(record):
    record = dict(record)
    record['created_at'] = record['created_at'].isoformat()
    if record.get("expiry", None):
        record['expiry'] = record['expiry'].isoformat()
    return record


REASON_LIMIT = 2000  # This is the set limit for the reason column in PostgreSQL.
router = APIRouter(prefix="/guilds", dependencies=requires_api_key)


@router.get("/{guild_id}/infractions")
async def get_guild_infractions(guild_id: int, request: Request):
    query = """SELECT * FROM infractions
               WHERE guild_id=$1
               ORDER BY id ASC;
            """
    record = await request.app.pool.fetch(query, guild_id)
    if not record:
        raise NotFound("Guild infractions")

    return list(map(serialize_infraction, record))


@router.put("/{guild_id}/infractions")
async def create_guild_infraction(guild_id: int, infraction: Infraction, request: Request):
    """Creates a new infraction.
    Returns a dict containing the ID of the newly created infraction"""
    if len(infraction.reason) > REASON_LIMIT:
        raise HTTPException(400, f"Reason is too long ({len(infraction.reason)}/{REASON_LIMIT})")

    if len(infraction.extra) == 0:
        query = """INSERT INTO infractions (guild_id, user_id, moderator_id, action, reason, created_at, expiry)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id;"""
        r = await request.app.pool.fetchval(query, infraction.guild_id, infraction.target_id, infraction.moderator_id, infraction.action.value,
                                            infraction.reason, infraction.created_at, infraction.expiry)
    else:
        query = """INSERT INTO infractions (guild_id, user_id, moderator_id, action, reason, created_at, expiry, extra)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   RETURNING id;"""
        r = await request.app.pool.fetchval(query, infraction.guild_id, infraction.target_id, infraction.moderator_id, infraction.action.value,
                                            infraction.reason, infraction.created_at, infraction.expiry, infraction.extra)

    return {"id": r}


@router.delete("/{guild_id}/infractions/{inf_id}")
async def delete_guild_infraction(guild_id: int, inf_id: int, request: Request):
    """Deletes a guild infraction"""
    query = """DELETE FROM infractions WHERE guild_id=$1 AND id=$2;"""
    r = await request.app.pool.execute(query, guild_id, inf_id)
    if r == "DELETE 0":
        raise NotFound(f"Infraction with ID {inf_id}")


@router.delete("/{guild_id}/users/{user_id}/infractions")
async def delete_guild_user_infractions(guild_id: int, user_id: int, request: Request):
    """Delete guild infractions for a user"""
    query = "DELETE FROM infractions WHERE guild_id=$1 AND user_id=$2;"
    r = await request.app.pool.execute(query, guild_id, user_id)
    if r == "DELETE 0":
        raise NotFound(message=f"User {user_id} has no infractions")


@router.get("/{guild_id}/users/{member_id}/infractions")
async def get_guild_user_infractions(guild_id: int, member_id: int, request: Request):
    """Gets infractions for a guild user."""
    # A guild user could be a member (the user is still in the guild) or a user (previous member of the guild)
    query = """SELECT * FROM infractions
               WHERE guild_id=$1
               AND user_id=$2
               ORDER BY id ASC;
            """
    records = await request.app.pool.fetch(query, guild_id, member_id)
    if not records:
        raise NotFound("Guild member infractions")

    return list(map(serialize_infraction, records))


@router.get("/{guild_id}/infractions/{inf_id}")
async def get_guild_infraction_id(guild_id: int, inf_id: int, request: Request):
    query = """SELECT * FROM infractions
               WHERE guild_id=$1
               AND id=$2;
            """
    record = await request.app.pool.fetchrow(query, guild_id, inf_id)
    if not record:
        raise NotFound("Guild infraction {inf_id}")

    return serialize_infraction(record)


@router.patch("/{guild_id}/infractions/{inf_id}")
async def patch_guild_infraction(guild_id: int, inf_id: int, inf: PatchableInfraction, request: Request):
    columns = []
    data = []

    if inf.reason:

        if len(inf.reason) > REASON_LIMIT:
            raise HTTPException(400, f"Reason is too long ({len(inf.reason)}/{REASON_LIMIT})")

        columns.append("reason")
        data.append(inf.reason)

    if inf.target_id:
        columns.append("target_id")
        data.append(inf.target_id)

    if inf.moderator_id:
        columns.append("moderator_id")
        data.append(inf.moderator_id)

    idx, update_query = build_update_query(columns)

    query = f"""UPDATE infractions
                SET {update_query}
                WHERE guild_id=${idx + 1} AND id=${idx + 2}
                RETURNING *"""
    resp = await request.app.pool.fetchrow(query, *data, guild_id, inf_id)

    if resp is None:
        raise NotFound(f"Infraction with ID {inf_id}")

    return resp
