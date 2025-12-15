import discord
from discord.ext import tasks, commands
import asyncio
import os
import random

# --- SECURE CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 1386989554682171392))
VC_ID = int(os.getenv("VC_ID", 1450026402815676446))
SONGS_FOLDER = "songs"

# --- Initialization ---
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
voice_client = None
song_list = []
is_playing_song = False
current_song_name = "Nothing"  # Currently playing song

# --- Song Handling ---
def load_songs():
    global song_list
    song_list.clear()
    if not os.path.isdir(SONGS_FOLDER):
        print(f"Folder {SONGS_FOLDER} missing!")
        return
    valid_extensions = ['.mp3', '.wav', '.flac']
    for filename in os.listdir(SONGS_FOLDER):
        if os.path.splitext(filename)[1].lower() in valid_extensions:
            song_list.append(os.path.join(SONGS_FOLDER, filename))
    print(f"Found {len(song_list)} songs.")

def after_song_finished(error):
    global is_playing_song
    is_playing_song = False
    if not play_next_song.is_running():
        play_next_song.start()

@tasks.loop(seconds=1)
async def play_next_song():
    global voice_client, is_playing_song, current_song_name

    if voice_client and voice_client.is_connected() and not voice_client.is_playing() and song_list and not is_playing_song:
        is_playing_song = True
        song_path = random.choice(song_list)
        current_song_name = os.path.basename(song_path)
        print(f"Now playing: {current_song_name}")

        if update_status.is_running():
            await update_status()

        try:
            source = discord.FFmpegPCMAudio(song_path)
            voice_client.play(source, after=after_song_finished)
        except Exception as e:
            print(f"Failed to play {current_song_name}: {e}")
            is_playing_song = False
            current_song_name = "Nothing"
    elif not song_list and play_next_song.is_running():
        print("No songs to play. Stopping music loop.")
        play_next_song.stop()
        current_song_name = "Nothing"
        if update_status.is_running():
            await update_status()

# --- Voice Channel Functions ---
async def join_channel():
    global voice_client
    guild = bot.get_guild(GUILD_ID)
    if guild:
        channel = guild.get_channel(VC_ID)
        if channel:
            try:
                if voice_client is None or not voice_client.is_connected():
                    voice_client = await channel.connect()
                    print("Joined voice channel.")
                    if song_list and not play_next_song.is_running():
                        play_next_song.start()
            except Exception as e:
                print("Failed to join:", e)

@tasks.loop(seconds=5)
async def keep_connected():
    if voice_client is None or not voice_client.is_connected():
        await join_channel()
    elif voice_client and voice_client.is_connected() and song_list and not play_next_song.is_running():
        play_next_song.start()

# --- Status Update Loop ---
@tasks.loop(minutes=10)
async def update_status():
    global current_song_name
    activity = discord.Activity(type=discord.ActivityType.listening, name=current_song_name)
    print(f"Updating status to: Listening to {current_song_name}")
    await bot.change_presence(activity=activity)

# --- Events ---
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'Logged in as {bot.user}')
    load_songs()
    await join_channel()
    keep_connected.start()
    if song_list:
        if not play_next_song.is_running():
            play_next_song.start()
        if not update_status.is_running():
            await update_status()
            update_status.start()


@bot.event
async def on_voice_state_update(member, before, after):
    global voice_client
    if member == bot.user:
        if before.channel and before.channel.id == VC_ID:
            if after.channel != before.channel:
                print("Disconnected! Rejoining...")
                await join_channel()

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    global voice_client, current_song_name
    if voice_client and voice_client.is_playing():
        voice_client.stop()  # triggers after_song_finished
        await interaction.response.send_message(f"Skipped: {current_song_name}")
        current_song_name = "Nothing"
    else:
        await interaction.response.send_message("No song is currently playing!")

# --- Run Bot ---
if not TOKEN:
    print("Error: DISCORD_TOKEN not found in environment variables.")
else:
    bot.run(TOKEN)
