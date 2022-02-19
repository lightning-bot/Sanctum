from __future__ import annotations

from typing import TYPE_CHECKING
from . import guilds

if TYPE_CHECKING:
    from fastapi import FastAPI

def setup_routers(app: FastAPI):
    app.include_router(guilds.router)