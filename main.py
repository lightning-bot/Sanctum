import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import config

from routers import guilds


app = FastAPI(version="1.0.0+v4")  # API version + bot version
app.include_router(guilds.router)


@app.on_event("startup")
async def on_startup():
    app.pool = await asyncpg.create_pool(config.POSTGRESQL_PSN)


@app.on_event("shutdown")
async def on_shutdown():
    await app.pool.close()
