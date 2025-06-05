import discord
from discord import app_commands
from discord.ext import commands
from config import botConfig, config

from classes.idea import Idea, Tag, Category
from handlers.loki_logging import get_logger


loki_logger = get_logger(
    "sphere.discord.python",
    level="debug",
    labels={
        "app": "sphere",
        "env": "dev",
        "service": "discord_bot",
        "lang": "python",
    }
)


class IdeaGroup(app_commands.Group):
    @app_commands.command(description="Create and add an idea")
    async def save(self, interaction: discord.Interaction, input: str):
        idea = Idea()
        tag = Tag()
        category = Category()
        
        tag.name = "network"        # dev purposes
        category.name = "tech"      # dev purposes
        
        idea.title = input
        idea.category = category
        
        await idea.store_into_db()
        
        await interaction.response.send_message(f"Added idea to the database")
        
        
class IdeaCommand(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        
    idea_group = IdeaGroup(name="idea", description="Create and store ideas.")
    
async def setup(client: commands.Bot) -> None:
    await client.add_cog(IdeaCommand(client=client), guild=discord.Object(id=botConfig["hub-server-guild-id"]))