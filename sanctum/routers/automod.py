from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional, TypedDict

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, root_validator, validator

from ..app import Request
from ..errors import NotFound
from ..security import requires_api_key

if TYPE_CHECKING:
    from typing_extensions import Self

router = APIRouter(prefix="/guilds", dependencies=requires_api_key)


# Models
class AutoModPunishmentModel(BaseModel):
    duration: Optional[int]  # This should be seconds
    type: Literal['DELETE', 'WARN', 'MUTE', 'KICK', 'BAN']


class AutoModEventModel(BaseModel):
    guild_id: int
    type: Literal['message-spam', 'mass-mentions', 'url-spam', 'invite-spam',
                  'message-content-spam', 'auto-dehoist', 'auto-normalize']
    count: int
    seconds: int
    ignores: Optional[List[int]] = []
    punishment: Optional[AutoModPunishmentModel]

    @root_validator
    def check_punishment(cls, values):
        _type, punishment = values.get("type"), values.get('punishment')
        if _type not in ("auto-dehoist", "auto-normalize") and punishment is None:
            raise ValueError(f'{_type} requires a punishment')
        return values

    class Config:
        schema_extra = {
            "example": {'guild_id': 540978015811928075, 'type': 'message-content-spam',
                        'count': 6, 'seconds': 11, 'ignores': [], 'punishment': {'type': 'BAN'}}
        }


class AutoModConfigResponse(BaseModel):
    guild_id: int
    default_ignores: List[int] = []
    warn_threshold: Optional[int] = None
    warn_punishment: Optional[Literal['KICK', 'BAN']] = None
    rules: List[AutoModEventModel] = []

    @validator('default_ignores', pre=True)
    def convert_to_default(cls, v):
        return v or []


@router.get("/{guild_id}/automod", response_model=AutoModConfigResponse)
async def get_automod_config(guild_id: int, request: Request):
    """Gets the guild's automod config and rules"""
    query = """
            SELECT config.*, COALESCE(json_agg(json_build_object('guild_id', rules.guild_id,
													 'type', rules.type,
													 'count', rules.count,
													 'seconds', rules.seconds,
													 'ignores', rules.ignores,
													 'punishment', punishment.*))
            FILTER (WHERE rules.guild_id IS NOT NULL), '[]'::json) AS rules FROM guild_automod_config AS config
            LEFT OUTER JOIN guild_automod_rules AS rules ON config.guild_id = rules.guild_id
            LEFT OUTER JOIN guild_automod_punishment AS punishment ON rules.id = punishment.id
            WHERE config.guild_id=$1
            GROUP BY config.guild_id;
            """
    record = await request.app.pool.fetchrow(query, guild_id)
    if not record:
        raise NotFound("Guild automod config")

    return record


class AutoModDefaultIgnoresResponse(TypedDict):
    default_ignores: List[int]


@router.put("/{guild_id}/automod/ignores", response_model=AutoModDefaultIgnoresResponse)
async def put_automod_default_ignores(guild_id: int, request: Request, ignores: List[int] = []):
    """Puts new automod default ignores"""
    if not ignores:
        query = "UPDATE guild_automod_config SET default_ignores=$2 WHERE guild_id=$1;"
        await request.app.pool.execute(query, guild_id, [])
        return {"default_ignores": []}

    query = """INSERT INTO guild_automod_config (guild_id, default_ignores)
               VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET
                  default_ignores = EXCLUDED.default_ignores
               RETURNING default_ignores;"""
    resp = await request.app.pool.fetchval(query, guild_id, ignores)
    return {"default_ignores": resp}


class AutoModEventDBModel(AutoModEventModel):
    id: int

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> Self:
        record = dict(record)
        return cls.parse_obj(record)


@router.get("/{guild_id}/automod/rules", response_model=List[AutoModEventDBModel])
async def get_guild_automod_rules(guild_id: int, request: Request) -> List[AutoModEventDBModel]:
    """Gets a guild's automod rule configuration"""
    query = """SELECT events.*, COALESCE(to_jsonb(punishment) - 'id', '{}'::jsonb) AS punishment FROM guild_automod_rules events
               LEFT OUTER JOIN guild_automod_punishment AS punishment ON events.id = punishment.id
               WHERE events.guild_id=$1;"""
    records = await request.app.pool.fetch(query, guild_id)
    if not records:
        raise NotFound("Guild automod rules")

    return list(map(AutoModEventDBModel.from_record, records))


class AddAutoModRuleResponse(TypedDict):
    id: int


@router.put("/{guild_id}/automod/rules", response_model=AddAutoModRuleResponse)
async def add_new_automod_rule(guild_id: int, event: AutoModEventModel, request: Request):
    async with request.app.pool.acquire() as conn:
        query = "SELECT * FROM guild_automod_rules WHERE guild_id=$1 AND type=$2 LIMIT 1;"
        r = await conn.fetchrow(query, guild_id, event.type)
        if r:
            raise HTTPException(409, "Rule already exists")

        async with conn.transaction():
            query = """INSERT INTO guild_automod_rules (guild_id, type, count, seconds, ignores)
                       VALUES ($1, $2, $3, $4, $5)
                       RETURNING id;"""
            rnum = await conn.fetchval(query, guild_id, event.type, event.count, event.seconds, event.ignores)

            if event.punishment:
                query = """INSERT INTO guild_automod_punishment (id, type, duration)
                           VALUES ($1, $2, $3);"""
                await conn.execute(query, rnum, event.punishment.type,
                                   event.punishment.duration)

    return {"id": rnum}


@router.delete("/{guild_id}/automod/rules/{event_name}")
async def delete_guild_automod_rule(guild_id: int, event_name: str, request: Request):
    query = """DELETE FROM guild_automod_rules WHERE guild_id=$1 AND type=$2;"""
    resp = await request.app.pool.execute(query, guild_id, event_name)
    if resp == "DELETE 0":
        raise NotFound(f"Guild automod config with event {event_name}")
    return {}
