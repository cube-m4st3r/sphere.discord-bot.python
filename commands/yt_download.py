import discord
from discord import app_commands
from discord.ext import commands
from config import botConfig, config
import pika
import yt_dlp
import os


class YtGroup(app_commands.Group):
    @app_commands.command(description="Download a YouTube (or YT Music) video with a provided URL")
    async def save(self, interaction: discord.Interaction, input: str):
        await interaction.response.defer()

        connection = pika.BlockingConnection(pika.ConnectionParameters(host=config["RMQ_HOST"], port=config["RMQ_PORT"]))
        channel = connection.channel()

        channel.queue_declare(queue=config["RMQ_YT_DOWNLOAD_QUEUE"])

        channel.basic_publish(exchange='',
                    routing_key=config["RMQ_YT_DOWNLOAD_QUEUE"],
                    body=input)

        connection.close()

        yt_info = await load_yt_info(url=input)
        yt_embed = await create_info_embed(yt_info=yt_info)

        await interaction.followup.send(embed=yt_embed)


async def load_yt_info(url: str) -> dict:
    print(url)
    cookie_file = config["YT_COOKIE_FILE"]
    ydl_opts = {"quiet": True, "skip_download": True}

    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file
    else:
        print("Cookiefile not found.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"Failed to extract video info for {url}: {e}")
        return

async def create_info_embed(yt_info: dict):
    embed = discord.Embed()
    embed.title = f"Added {yt_info['title']} to the queue"
    #embed.colour(discord.Color.green)

    return embed

class YouTubeDownload(commands.Cog):
        def __init__(self, client: commands.Bot):
            self.client = client

        yt_group = YtGroup(name="youtube", description="YouTube (Music) related commands.")

async def setup(client: commands.Bot) -> None:
    await client.add_cog(YouTubeDownload(client=client), guild=discord.Object(id=botConfig["hub-server-guild-id"]))