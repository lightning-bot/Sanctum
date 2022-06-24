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
