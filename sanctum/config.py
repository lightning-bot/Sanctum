import json
import os


class Config:
    def __init__(self) -> None:
        if os.path.exists("config.json"):
            with open("config.json") as fp:
                data = json.load(fp)
        else:
            data = {}

        self.postgres = os.getenv("POSTGRESQL_DSN", data.get("POSTGRESQL_DSN", None))

        if not self.postgres:
            raise Exception("Missing required configuration key \"POSTGRESQL_DSN\"")

        key = os.getenv("API_KEY", data.get("API_KEY", None))
        if not key:
            raise Exception("Missing required configuration key \"API_KEY\"")

        self.keys = [key]

        self.shlink_key = os.getenv("SHLINK_KEY", data.get("SHLINK_KEY", None))
