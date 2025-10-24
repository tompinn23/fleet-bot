from bot.config import load
import hikari
import asyncio
import arc
import logging
import os
import bot.db as db
from bot.messages import MessageListener

logging.basicConfig(
    level=logging.INFO,  # capture everything from DEBUG up
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

config_path = os.environ.get("FLEET_CONFIG", "config.toml")

config = load(config_path)
# intents = discord.Intents.default()
bot = hikari.GatewayBot(token=config.bot.token)
client = arc.GatewayClient(bot, default_enabled_guilds=[config.bot.guild])

listener = MessageListener(bot, config)



client.load_extension("bot.cmds.link")
client.load_extension("bot.cmds.register")

@bot.listen(hikari.StartedEvent)
async def on_ready(event: hikari.StartedEvent) -> None:
    client.set_type_dependency(db.GuildPool, await db.db_init(config))
    listener.start()
    user = bot.get_me()
    print(f"Logged in as {user.username}")

@bot.listen(hikari.StoppingEvent)
async def on_stopping(event: hikari.StoppingEvent) -> None:
    await listener.shutdown()

def main():
    bot.run()

if __name__ == "__main__":
    main()

