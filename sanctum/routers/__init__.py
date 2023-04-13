from __future__ import annotations

from typing import TYPE_CHECKING

from . import admin, automod, config, guilds, infractions, reports, timers

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_routers(app: FastAPI):
    app.include_router(guilds.router)
    app.include_router(timers.router)
    app.include_router(infractions.router)
    app.include_router(config.router)
    app.include_router(automod.router)
    app.include_router(admin.router)
    app.include_router(reports.router)
