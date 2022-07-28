from typing import Optional

from fastapi import APIRouter, Request

from ..errors import NotFound
from ..security import requires_api_key

router = APIRouter(prefix="/guilds", dependencies=requires_api_key)


@router.get("/{guild_id}/config")
async def get_bot_config(guild_id: int, request: Request):
    query = """SELECT * FROM guild_config
               WHERE guild_id=$1;"""
    record = await request.app.pool.fetchrow(query, guild_id)
    if not record:
        raise NotFound("Guild bot config")

    return record


@router.get("/{guild_id}/prefixes")
async def get_guild_prefixes(guild_id: int, request: Request):
    query = """SELECT prefixes
               FROM guild_config
               WHERE guild_id=$1;
            """
    record = await request.app.pool.fetchval(query, guild_id)
    if not record:
        raise NotFound("Guild prefixes")

    return record


@router.put("/{guild_id}/prefixes")
async def put_guild_prefixes(guild_id: int, request: Request, prefixes: Optional[list] = None):
    """Upserts new prefixes"""
    if not prefixes:
        query = "UPDATE guild_config SET prefixes = NULL WHERE guild_id=$1;"
        await request.app.pool.execute(query, guild_id)
        return {}

    query = """INSERT INTO guild_config (guild_id, prefixes)
               VALUES ($1, $2::text[]) ON CONFLICT (guild_id)
               DO UPDATE SET
                   prefixes = EXCLUDED.prefixes;
            """
    await request.app.pool.execute(query, guild_id, list(prefixes))
    return {}
