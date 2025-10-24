import arc
import secrets
from datetime import datetime, timedelta

from hikari import MessageFlag
import bot.db as db

plugin = arc.GatewayPlugin("link")


def link_token() -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)
    )


@plugin.include
@arc.slash_command("link", "link the companion app")
async def link_cmd(ctx: arc.GatewayContext, pool: db.GuildPool = arc.inject()) -> None:
    token = link_token()
    async with pool.acquire() as connection:
        await connection.execute(
            "INSERT into link_codes VALUES ($1, $2, false, $3, $4)",
            token,
            datetime.now() + timedelta(minutes=4),
            ctx.user.id,
            ctx.guild_id,
        )
    try:
        await ctx.user.send(f"Your link code is ```{token}```")
    except:
        await ctx.respond(
            f"❌ Failed to send your DM (am I allowed?)", flags=MessageFlag.EPHEMERAL
        )

    await ctx.respond("✔️ Sent you a DM", flags=MessageFlag.EPHEMERAL)


@arc.loader
def loader(client: arc.GatewayClient) -> None:
    client.add_plugin(plugin)


@arc.unloader
def unloader(client: arc.GatewayClient) -> None:
    client.remove_plugin(plugin)
