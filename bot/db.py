import asyncpg
from asyncpg.pool import PoolAcquireContext
from bot.config import Config
from typing import Optional
import hikari


class GuildConnection:
    def __init__(self, pool: asyncpg.pool.Pool, guild: hikari.Snowflake):
        self.pool = pool
        self.guild = guild

    async def __aenter__(self) -> asyncpg.Connection:
        self.conn = await self.pool.acquire()
        await self.conn.execute(f"SET app.guild_id = {self.guild}")
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.conn.execute("RESET app.guild_id")
        finally:
            await self.pool.release(self.conn)


class GuildPool:
    def __init__(self, pool: asyncpg.pool.Pool):
        self.pool = pool

    def acquire(
        self, guild: hikari.Snowflake | None = hikari.Snowflake(0)
    ) -> GuildConnection | PoolAcquireContext:
        if guild is not None and guild != 0:
            return GuildConnection(self.pool, guild)
        else:
            return self.pool.acquire()

    async def release(self, conn: GuildConnection):
        await self.pool.release(conn.conn)

    async def close(self):
        await self.pool.close()


pool: Optional[GuildPool] = None


async def db_init(config: Config) -> GuildPool:
    global pool
    _pool = await asyncpg.pool.create_pool(str(config.database.url))
    pool = GuildPool(_pool)
    return pool


async def get_db() -> GuildPool:
    if pool is None:
        raise Exception("Pool is null")
    return pool
