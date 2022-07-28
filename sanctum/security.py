from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from .config import Config

auth_key = APIKeyHeader(name="X-API-Key")
config = Config()


@dataclass
class User:
    """Represents an authenticated user"""
    username: str
    token: str


def validate_api_key(key: str = Depends(auth_key)):
    if key not in config.keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Users
    return User("admin", key)


requires_api_key = [Depends(validate_api_key)]
