import asyncpg
from fastapi import FastAPI
from starlette.requests import Request as StarRequest


class API(FastAPI):
    pool: asyncpg.Pool


class Request(StarRequest):
    app: API
