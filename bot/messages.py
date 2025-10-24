import asyncio
from datetime import datetime
import logging
from typing import cast
import hikari
import json
import asyncpg


from bot.config import Config
import aio_pika

def contains(list, filter):
    for x in list:
        if filter(x):
            return True
    return False

class MessageListener:

    bot: hikari.GatewayBot
    config: Config
    pool: asyncpg.pool.Pool

    def __init__(self, bot: hikari.GatewayBot, config: Config):
        self.bot = bot
        self.config = config
        self._consumer_task = None
        self._shutdown_event = asyncio.Event()

    def start(self):
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self.consume())
            logging.info("Started consuming messages")
        return self._consumer_task

    async def shutdown(self):
        self._shutdown_event.set()

        if self._consumer_task and not self._consumer_task.done():
            try:
                await asyncio.wait_for(self._consumer_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

    async def consume(self):
        try:
            self.pool = await asyncpg.pool.create_pool(self.config.database.admin_url.encoded_string())
            connection = await aio_pika.connect_robust(self.config.queue.url.encoded_string())
            logging.info("Connected to RabbitMQ")

            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)

            queue = await channel.declare_queue("jump_logs", durable=True)

            logging.info("Waiting for messages from queue: \"jump_logs\"")
            await queue.consume(self.process)

            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.error(f"error processing message: {e}")
            raise
        finally:
            if connection and not connection.is_closed:
                await connection.close()


    async def process(self, message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process():
            try:
                body = message.body.decode()
                logging.info(f"Received: {body}")

                try:
                    data = json.loads(body)
                    callsign = data.get("callsign")
                    action = data.get("action")
                    async with self.pool.acquire() as conn:
                        ids = await conn.fetch("SELECT name, uid, guild_id FROM carriers WHERE callsign = $1", callsign)
                        for id in ids:
                            name = f"🚀{id["name"].replace(' ', '-')}-{callsign}".lower()
                            ch = await self.carrier_channel(name, id["uid"], id["guild_id"])
                            departure: datetime = datetime.fromisoformat(data.get("departure"))
                            logging.info(f"Finding jump log entry with callsign={callsign} departure={departure}")
                            row = await conn.fetchrow("SELECT start, destination, destination_body FROM jump_log WHERE callsign = $1 AND departure = $2", callsign, departure)
                            if row is None:
                                continue
                            body = row["destination_body"]
                            if body is None:
                                body = ""
                            else:
                                body = f"({body})"
                            
                            msg = None
                            if action == "plotting":
                                msg = f"Hey <@{id["uid"]}>\n**{id["name"]} ({callsign})** is plotting to {row["destination"]} {body} from {row["start"]} and leaves <t:{int(departure.timestamp())}:R>"
                            elif action == "cancelled":
                                msg = f"Hey <@{id["uid"]}>\n**{id["name"]} ({callsign})** has cancelled its jump to {row["destination"]} {body} from {row["start"]}"
                            elif action == "completed":
                                msg = f"Hey <@{id["uid"]}>\n**{id["name"]} ({callsign})** has completed its jump to {row["destination"]} {body} from {row["start"]}"


                            if msg is not None:
                                logging.info(f"sending carrier message {msg}")
                                await ch.send(msg)
                except json.JSONDecodeError as e:
                    logging.error(f"JSON error {e}")
            except Exception as e:
                logging.error(f"Exception {e}")

    async def carrier_channel(self, name: str, uid: int, guild_id: int) -> hikari.GuildTextChannel:
        channels = await self.bot.rest.fetch_guild_channels(guild_id)
        guild = await self.bot.rest.fetch_guild(guild_id)
        everyone = guild.get_role(guild.id)
        channel = None
        category = None
        for x in channels:
            if (x.type == hikari.ChannelType.GUILD_CATEGORY and x.name == "Carrier Updates"):
                category = cast(hikari.GuildCategory, x)
            if (x.type == hikari.ChannelType.GUILD_TEXT and x.name == name):
                channel = cast(hikari.GuildTextChannel, x)
            if channel is not None and category is not None:
                break
        if category is None:
            category = await self.bot.rest.create_guild_category(guild_id, "Carrier Updates")
        if channel is None:                  
            channel = await self.bot.rest.create_guild_text_channel(guild_id, name, category=category)
        overwrites = [
            hikari.PermissionOverwrite(
                id=everyone.id,
                type=hikari.PermissionOverwriteType.ROLE,
                deny=hikari.Permissions.VIEW_CHANNEL
            ),
            hikari.PermissionOverwrite(
                id=uid,
                type=hikari.PermissionOverwriteType.MEMBER,
                allow=hikari.Permissions.VIEW_CHANNEL | hikari.Permissions.READ_MESSAGE_HISTORY
            ),
            hikari.PermissionOverwrite(
                id=self.bot.get_me().id,
                type=hikari.PermissionOverwriteType.MEMBER,
                allow=(
                    hikari.Permissions.VIEW_CHANNEL |
                    hikari.Permissions.SEND_MESSAGES |
                    hikari.Permissions.EMBED_LINKS |
                    hikari.Permissions.READ_MESSAGE_HISTORY |
                    hikari.Permissions.MANAGE_CHANNELS  # To edit later if needed
                )
            )
        ]
        await channel.edit(permission_overwrites=overwrites)

        return channel

