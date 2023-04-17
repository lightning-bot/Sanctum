from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..utils import build_update_query
from ..app import Request
from ..errors import NotFound
from ..security import requires_api_key


class MessageReporter(BaseModel):
    author_id: int
    reason: str
    original: bool = False


class MessageReport(BaseModel):
    guild_id: int
    channel_id: int
    message_id: int
    report_message_id: int
    reporter: MessageReporter


class PatchableMessageReport(BaseModel):
    dismissed: Optional[bool] = None
    actioned: Optional[bool] = None


def serialize_reporter(record):
    record = dict(record)
    record['reported_at'] = record['reported_at'].isoformat()
    return record


router = APIRouter(prefix="/guilds", dependencies=requires_api_key)


@router.get("/{guild_id}/reports/{message_id}")
async def get_guild_message_report(guild_id: int, message_id: int,
                                   request: Request):
    query = "SELECT * FROM message_reports WHERE guild_id=$1 AND message_id=$2;"
    record = await request.app.pool.fetchrow(query, guild_id, message_id)
    if not record:
        raise NotFound("Message report")

    return dict(record)


@router.put("/{guild_id}/reports")
async def create_guild_message_report(guild_id: int, payload: MessageReport,
                                      request: Request):
    query = """INSERT INTO message_reports (guild_id, message_id, channel_id, report_message_id)
               VALUES ($1, $2, $3, $4)
               RETURNING id;"""
    record = await request.app.pool.fetchrow(query, guild_id,
                                             payload.message_id,
                                             payload.channel_id,
                                             payload.report_message_id)

    query = """INSERT INTO message_reporters (guild_id, message_id, author_id, reason, original)
               VALUES ($1, $2, $3, $4, $5);"""
    await request.app.pool.execute(query, guild_id, payload.message_id,
                                   payload.reporter.author_id,
                                   payload.reporter.reason, True)

    return {"id": record['id']}


@router.put("/{guild_id}/reports/{message_id}/reporters")
async def put_guild_message_reporter(guild_id: int, message_id: int,
                                     payload: MessageReporter, request: Request):
    query = """INSERT INTO message_reporters (guild_id, message_id, author_id, reason, original)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (message_id, author_id)
               DO UPDATE SET reason = EXCLUDED.reason
               RETURNING guild_id, message_id, author_id, reason, original, reported_at;"""
    record = await request.app.pool.fetchrow(query, guild_id, message_id,
                                             payload.author_id, payload.reason,
                                             payload.original)

    return serialize_reporter(record)


@router.get("/{guild_id}/reports/{message_id}/reporters")
async def get_guild_message_reporters(guild_id: int, message_id: int,
                                      request: Request):
    query = "SELECT * FROM message_reporters WHERE guild_id=$1 AND message_id=$2;"
    records = await request.app.pool.fetch(query, guild_id, message_id)
    if not records:
        raise NotFound("Message report")

    return list(map(serialize_reporter, records))


@router.patch("/{guild_id}/reports/{message_id}")
async def edit_guild_message_report(guild_id: int, message_id: int,
                                    report: PatchableMessageReport,
                                    request: Request):
    columns = []
    data = []

    if report.actioned is not None:
        columns.append("actioned")
        data.append(report.actioned)

    if report.dismissed is not None:
        columns.append("dismissed")
        data.append(report.dismissed)

    if not data:
        raise HTTPException(400, "Payload was empty")

    idx, update_query = build_update_query(columns)

    query = f"""UPDATE message_reports
                SET {update_query}
                WHERE guild_id=${idx + 1} AND message_id=${idx + 2}
                RETURNING id, guild_id, message_id, channel_id, report_message_id, dismissed, actioned"""
    resp = await request.app.pool.fetchrow(query, *data, guild_id, message_id)

    if resp is None:
        raise NotFound(f"Message report with message id {message_id}")

    return resp
