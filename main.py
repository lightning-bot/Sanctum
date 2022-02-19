import asyncpg
from fastapi import FastAPI

import config

from routers import setup_routers


app = FastAPI(title="Sanctum",
              version="1.0.0+v4",  # API version + bot version
              redoc_url="/docs", docs_url=None)
setup_routers(app)


@app.on_event("startup")
async def on_startup():
    app.pool = await asyncpg.create_pool(config.POSTGRESQL_PSN)


@app.on_event("shutdown")
async def on_shutdown():
    await app.pool.close()
