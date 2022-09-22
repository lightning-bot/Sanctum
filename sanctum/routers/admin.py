from __future__ import annotations

from typing import TypedDict

import httpx
import privatebinapi
from fastapi import APIRouter
from pydantic import BaseModel
from sanctum.config import Config

from sanctum.errors import NotFound
from sanctum.security import requires_api_key

from ..app import Request


class _Router(APIRouter):
    session: httpx.AsyncClient


router = _Router(prefix="/admin", dependencies=requires_api_key)


@router.on_event('startup')
async def on_startup():
    cfg = Config()
    if cfg.shlink_key:
        headers = {"X-API-Key": cfg.shlink_key}
    else:
        headers = None
    router.session = httpx.AsyncClient(headers=headers)


@router.on_event('shutdown')
async def on_shutdown():
    await router.session.aclose()


class PasteBinPayload(BaseModel):
    text: str


class PasteResponse(TypedDict):
    full_url: str


async def create_shortened_link(link: str) -> str:
    resp = await router.session.post("https://short.lightsage.dev/rest/v3/short-urls", data={"longUrl": link})
    r = resp.json()
    return r['shortUrl']


@router.put("/paste", response_model=PasteResponse)
async def create_paste(payload: PasteBinPayload, request: Request):
    """Creates a paste with given text"""
    resp = await privatebinapi.send_async("https://paste.lightsage.dev/",
                                          text=payload.text,
                                          formatting="syntaxhighlighting",
                                          expiration="1month")

    if router.session.headers.get("X-API-Key", None):
        url = await create_shortened_link(resp['full_url'])
    else:
        url = resp['full_url']

    query = """INSERT INTO pastes (url, delete_token)
               VALUES ($1, $2);"""
    await request.app.pool.execute(query, url, resp['deletetoken'])

    return {'full_url': url}


@router.delete("/paste")
async def delete_paste(url: str, request: Request) -> None:
    """Deletes a paste by url"""
    query = "SELECT delete_token FROM pastes WHERE url=$1;"
    delete_token = await request.app.pool.fetchval(query, url)
    if not delete_token:
        raise NotFound("Paste")

    await privatebinapi.delete_async(url, delete_token)
