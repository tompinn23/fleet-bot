from discord.ext import commands
import discord
from discord import InteractionContextType
import secrets
from datetime import datetime, timedelta
from bot.db import pool
import asyncpg
import logging


class LinkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_link_token(self, groups=6, chars_per_group=4, sep="-") -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return sep.join(
            "".join(secrets.choice(alphabet) for _ in range(chars_per_group))
            for _ in range(groups)
        )

    @discord.slash_command(
        description="Link companion app",
        contexts=[InteractionContextType.guild, InteractionContextType.bot_dm],
    )
    async def link(self, interaction: discord.Interaction):
        token = self.generate_link_token()
        logging.info(f"generating link token for {interaction.user.name}")
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO link_codes VALUES ($1, $2, $3, false)",
                    token,
                    datetime.now() + timedelta(minutes=4),
                    interaction.user.id,
                )
        except asyncpg.PostgresError as e:
            logging.error(f"failed to generate and insert link token: {e}")
            await interaction.response.send_message("❌ Internal Error", ephemeral=True)
            return

        try:
            await interaction.user.send(f"Your link code is:\n```{token}```")
            await interaction.response.send_message("✅ DM sent!", ephemeral=True)
        except Exception as e:
            logging.error(f"failed to send DM to {interaction.user.name} {e}")
            await interaction.response.send_message(
                "❌ Failed to send DM", ephemeral=True
            )


async def setup(bot: commands.Bot):
    bot.add_cog(LinkCog(bot))
