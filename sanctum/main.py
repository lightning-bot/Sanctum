import asyncpg
import asyncio
import orjson
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, ORJSONResponse

from .app import API, Request
from .config import Config
from .errors import NotFound
from .routers import setup_routers

app = API(title="Sanctum",
          version="1.0.0+v4",  # API version + bot version
          redoc_url=None, docs_url="/docs2")
setup_routers(app)


@app.exception_handler(NotFound)
async def not_found_exception_handler(request: Request, exc: NotFound):
    return ORJSONResponse(status_code=404, content={"message": f"{exc.thing} was not found!" if exc.thing else exc.message})


@app.exception_handler(409)
async def conflict_exc_handler(request: Request, exc: HTTPException):
    return ORJSONResponse(status_code=409, content={"message": exc.detail})


def encode_json(data):
    return orjson.dumps(data).decode('utf-8')


@app.on_event("startup")
async def on_startup():
    config = Config()

    async def init(connection: asyncpg.Connection):
        await connection.set_type_codec('json', encoder=encode_json, decoder=orjson.loads, schema='pg_catalog')
        await connection.set_type_codec('jsonb', encoder=encode_json, decoder=orjson.loads, schema='pg_catalog')

    try:
        app.pool = await asyncpg.create_pool(config.postgres, init=init)
    except Exception as e:
        print(e)
        loop = asyncio.get_running_loop()
        loop.stop()


@app.on_event("shutdown")
async def on_shutdown():
    await app.pool.close()


@app.get("/docs", include_in_schema=False, dependencies=None)
async def docs():
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <script type="module" src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
  </head>
  <body>
    <rapi-doc spec-url="{app.openapi_url}"> </rapi-doc>
  </body>
</html>"""
    return HTMLResponse(html)
