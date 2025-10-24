from enum import auto
import logging
import arc
from hikari import (
    InternalServerError,
    MessageFlag,
    NotFoundError,
    RateLimitTooLongError,
    UnauthorizedError,
)
import hikari
import bot.db as db
from urllib.parse import quote

from bot.config import FC_HEADER

plugin = arc.GatewayPlugin("register")


@plugin.include
@arc.slash_command("register", "register a carrier")
async def register_cmd(
    ctx: arc.GatewayContext,
    callsign: arc.Option[str, arc.StrParams("callsign")],
    pool: db.GuildPool = arc.inject(),
) -> None:
    async with pool.acquire(ctx.guild_id) as conn:
        if await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM carriers WHERE callsign = $1 AND uid = $2)",
            callsign,
            ctx.user.id,
        ):
            await ctx.respond(
                f"The carrier {callsign} is already registered to you",
                flags=MessageFlag.EPHEMERAL,
            )
            return
        uid = await conn.fetchval(
            "SELECT uid FROM carriers WHERE callsign = $1", callsign
        )
        if uid is not None:
            username = "Unknown"
            try:
                user = await ctx.client.rest.fetch_user(uid)
                username = user.username
            except (
                NotFoundError
                | UnauthorizedError
                | RateLimitTooLongError
                | InternalServerError
            ):
                pass
            await ctx.respond(
                f"The carrier {callsign} is already registered to {username}",
                flags=MessageFlag.EPHEMERAL,
            )
            return

        result = await conn.execute(
            "INSERT INTO carriers (callsign, uid, guild_id) VALUES ($1, $2, $3)",
            callsign,
            ctx.user.id,
            ctx.guild_id,
        )
        logging.info(f"added new carrier {result}")
        if result == "INSERT 0 1":
            await ctx.respond(
                f"Carrier {callsign} has been sucessfully registered with you",
                flags=MessageFlag.EPHEMERAL,
            )
        else:
            await ctx.respond(
                f"Unable to register carrier {callsign}", flags=MessageFlag.EPHEMERAL
            )

async def provide_callsigns(data: arc.AutocompleteData[arc.GatewayClient, str], pool: db.GuildPool = arc.inject()) -> list[str]:
    async with pool.acquire(data.guild_id) as conn:
        rows = await conn.fetch("SELECT callsign FROM carriers WHERE callsign LIKE $1", data.focused_value.upper() + "%")
        if rows is None:
            return []
        return [x["callsign"] for x in rows if "callsign" in x]

@plugin.include
@arc.slash_command("carrier", "find carrier information")
async def carrier_cmd(
    ctx: arc.GatewayContext,
    callsign: arc.Option[str, arc.StrParams("callsign", autocomplete_with=provide_callsigns)],
    pool: db.GuildPool = arc.inject(),
) -> None:
    async with pool.acquire(ctx.guild_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM carriers WHERE callsign = $1", callsign.upper()
        )
        if row is None:
            await ctx.respond("Unable to find the carrier", flags=MessageFlag.EPHEMERAL)
            return

        embed = hikari.Embed(title=f"{row['name'] or 'Unknown'} [{row['callsign']}]")
        if row["location"] is not None:
            location = f"[{row['location']}](https://inara.cz/elite/starsystem/?search={quote(row['location'])})"
        else:
            location = "The Milky Way"
        embed.add_field("Location", location)
        embed.add_field(
            "Fuel",
            f"{str(row['fuel']) + '/1000' if row['fuel'] is not None else 'Trit Crew spaced'}",
            inline=True,
        )
        embed.add_field(
            "Cargo",
            f"{str(row['cargo']) + '/25000' if row['cargo'] is not None else 'eh?'}",
            inline=True,
        )
        file = hikari.Bytes(FC_HEADER, "fc_header.jpg")
        embed.set_image(file)
        await ctx.respond(embed=embed)


@arc.loader
def loader(client: arc.GatewayClient) -> None:
    client.add_plugin(plugin)


@arc.unloader
def unloader(client: arc.GatewayClient) -> None:
    client.remove_plugin(plugin)
