from pydantic import BaseModel, PostgresDsn, AmqpDsn
import tomllib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "assets", "fc_header.jpg"), "rb") as f:
    FC_HEADER = f.read()


class DatabaseConfig(BaseModel):
    url: PostgresDsn
    admin_url: PostgresDsn


class QueueConfig(BaseModel):
    url: AmqpDsn


class BotConfig(BaseModel):
    token: str
    guild: int


class Config(BaseModel):
    database: DatabaseConfig
    queue: QueueConfig
    bot: BotConfig


def load(path: str = "config.toml") -> Config:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config(**data)
