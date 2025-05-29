import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import botConfig, config
from prefect.blocks.system import Secret
import dateparser
import datetime
from classes.reminder import Reminder


async def parse_time_naturally(text: str) -> datetime:
    dt = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if dt is None:
        raise ValueError("Could not parse the time string.")
    return dt

async def send_due_reminders(self):
    reminders = await Reminder.load_due_reminders()
    for reminder in reminders:
        try:
            user = await self.fetch_user(reminder.discord_user_id)
        except discord.NotFound:
            print(f"User {reminder.discord_user_id} not found via fetch_user")
            user = None
        except discord.HTTPException as e:
            print(f"HTTP error fetching user {reminder.discord_user_id}: {e}")
            user = None

        if user:
            try:
                await user.send(f"⏰ Reminder: {reminder.message}")
                await reminder.mark_as_sent()
            except Exception as e:
                print(f"Failed to send reminder to user {reminder.discord_user_id}: {e}")
        else:
            print(f"User {reminder.discord_user_id} could not be retrieved")

class ToolsGroup(app_commands.Group):
    @app_commands.command(description="Remind yourself with a message.")
    @app_commands.describe(time="When to remind (e.g. 'in 1h')", message="What to remind you about")
    async def remind(self, interaction: discord.Interaction, time: str, message: str):
        remind_time= await parse_time_naturally(time)
        obj = Reminder.load_from_input(discord_user_id=interaction.user.id, message=message, remind_at=remind_time)
        await obj.store_into_db()

        await interaction.response.send_message(f"⏰ Reminder `{message}` set for <t:{int(remind_time.timestamp())}:R>!", ephemeral=True)


class ToolsCommand(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    tools_group = ToolsGroup(name="tool", description="Useful tools.")

async def setup(client: commands.Bot) -> None:
    await client.add_cog(ToolsCommand(client=client), guild=discord.Object(id=botConfig["hub-server-guild-id"]))