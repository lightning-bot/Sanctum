import asyncpg
import orjson
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import config
from routers import setup_routers

app = FastAPI(title="Sanctum",
              version="1.0.0+v4",  # API version + bot version
              redoc_url=None, docs_url="/docs2")
setup_routers(app)


@app.on_event("startup")
async def on_startup():
    async def init(connection: asyncpg.Connection):
        await connection.set_type_codec('json', encoder=orjson.dumps, decoder=orjson.loads, schema='pg_catalog')
        await connection.set_type_codec('jsonb', encoder=orjson.dumps, decoder=orjson.loads, schema='pg_catalog')
    app.pool = await asyncpg.create_pool(config.POSTGRESQL_PSN, init=init)


@app.on_event("shutdown")
async def on_shutdown():
    await app.pool.close()


@app.get("/docs", include_in_schema=False)
async def docs():
    html = f"""<!doctype html> <!-- Important: must specify -->
<html>
  <head>
    <meta charset="utf-8"> <!-- Important: rapi-doc uses utf8 characters -->
    <script type="module" src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
  </head>
  <body>
    <rapi-doc spec-url="{app.openapi_url}"> </rapi-doc>
  </body>
</html>"""
    return HTMLResponse(html)
