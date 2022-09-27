from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, TypedDict

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel

from ..app import Request
from ..errors import NotFound
from ..security import requires_api_key

if TYPE_CHECKING:
    from typing_extensions import Self

router = APIRouter(prefix="/guilds", dependencies=requires_api_key)


class AutoModConfigResponse(TypedDict):
    guild_id: int
    default_ignores: List[int]


@router.get("/{guild_id}/automod", response_model=AutoModConfigResponse)
async def get_automod_config(guild_id: int, request: Request):
    """Gets the base automod config"""
    query = "SELECT * FROM guild_automod_config WHERE guild_id=$1;"
    record = await request.app.pool.fetchrow(query, guild_id)
    if not record:
        raise NotFound("Guild automod config")

    return record


class AutoModDefaultIgnoresResponse(TypedDict):
    default_ignores: List[int]


@router.put("/{guild_id}/automod/ignores", response_model=AutoModDefaultIgnoresResponse)
async def put_automod_default_ignores(guild_id: int, ignores: List[int], request: Request):
    """Puts new automod default ignores"""
    query = """INSERT INTO guild_automod_config (guild_id, default_ignores)
               VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET
                  default_ignores = EXCLUDED.default_ignores
               RETURNING default_ignores;"""
    resp = await request.app.pool.fetchval(query, guild_id, ignores)
    return {"default_ignores": resp}


# Rules...
class AutoModPunishmentModel(BaseModel):
    duration: Optional[int]
    type: str


class AutoModEventModel(BaseModel):
    guild_id: int
    type: str
    count: int
    seconds: int
    ignores: Optional[List[int]] = []
    punishment: AutoModPunishmentModel

    class Config:
        schema_extra = {
            "example": {'guild_id': 540978015811928075, 'type': 'message-content-spam',
                        'count': 6, 'seconds': 11, 'ignores': [], 'punishment': {'type': 'BAN'}}
        }


class AutoModEventDBModel(AutoModEventModel):
    id: int

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> Self:
        record = dict(record)
        if record['punishment_type'] is not None:
            record['punishment'] = {"duration": record.pop('punishment_duration'), "type": record.pop("punishment_type")}

        return cls.parse_obj(record)


@router.get("/{guild_id}/automod/rules", response_model=List[AutoModEventDBModel])
async def get_guild_automod_rules(guild_id: int, request: Request) -> List[AutoModEventDBModel]:
    """Gets a guild's automod rule configuration"""
    query = """SELECT events.*, punishment.duration AS punishment_duration, punishment.type AS punishment_type FROM guild_automod_rules events
               INNER JOIN guild_automod_punishment AS punishment ON events.id = punishment.id
               WHERE events.guild_id=$1;"""
    records = await request.app.pool.fetch(query, guild_id)
    if not records:
        raise NotFound("Guild automod rules")

    return list(map(AutoModEventDBModel.from_record, records))


class AddAutoModRuleResponse(TypedDict):
    id: int


@router.put("/{guild_id}/automod/rules", response_model=AddAutoModRuleResponse)
async def add_new_automod_rules(guild_id: int, event: AutoModEventModel, request: Request):
    query = """INSERT INTO guild_automod_rules (guild_id, type, count, seconds, ignores)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id;"""
    rnum = await request.app.pool.fetchval(query, guild_id, event.type, event.count, event.seconds, event.ignores)
    query = """INSERT INTO guild_automod_punishment (id, type, duration)
               VALUES ($1, $2, $3);"""
    await request.app.pool.execute(query, rnum, event.punishment.type,
                                   event.punishment.duration)

    return {"id": rnum}


@router.delete("/{guild_id}/automod/rules/{event_name}")
async def delete_guild_automod_rule(guild_id: int, event_name: str, request: Request):
    query = """DELETE FROM guild_automod_rules WHERE guild_id=$1 AND type=$2;"""
    resp = await request.app.pool.execute(query, guild_id, event_name)
    if resp == "DELETE 0":
        raise NotFound(f"Guild automod config with event {event_name}")
    return {}
