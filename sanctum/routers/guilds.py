from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, validator

from ..errors import NotFound


class GuildPayload(BaseModel):
    name: str
    owner_id: int
    left_at: Optional[datetime]

    @validator('left_at', pre=True)
    def dt_validator(cls, value):
        if not value:
            return value
        return value.replace(tzinfo=timezone.utc)


class Guild(GuildPayload):
    id: int


router = APIRouter(prefix="/guilds")


@router.get("/{guild_id}", response_model=Guild)
async def get_guild(guild_id: int, request: Request):
    """Gets a guild"""
    query = """SELECT * FROM guilds
               WHERE id=$1;
            """
    record = await request.app.pool.fetchrow(query, guild_id)
    if not record:
        raise NotFound("Guild")

    return dict(record)


@router.put("/{guild_id}")
async def create_guild(guild_id: int, guild: GuildPayload, request: Request):
    """Creates or updates a guild"""
    query = """INSERT INTO guilds (id, name, owner_id)
               VALUES ($1, $2, $3)
               ON CONFLICT (id) DO UPDATE
               SET name = EXCLUDED.name, owner_id = EXCLUDED.owner_id, left_at = NULL;
            """
    await request.app.pool.execute(query, guild_id, guild.name, guild.owner_id)


@router.delete("/{guild_id}/leave")
async def mark_guild_leave(guild_id: int, request: Request):
    query = "UPDATE guilds SET left_at=(NOW() AT TIME ZONE 'utc') WHERE id=$1;"
    await request.app.pool.execute(query, guild_id)
