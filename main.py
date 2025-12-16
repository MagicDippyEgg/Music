import discord
from discord.ext import tasks, commands
import os
import random
import shutil
import traceback
from discord import app_commands
from discord.utils import get

# --- CONFIG (safe parsing) ---
def env_int(name, default):
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except Exception:
        print(f"Warning: env var {name} value {v!r} is not an int. Using default {default}.")
        return default

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = env_int("GUILD_ID", 1386989554682171392)
VC_ID = env_int("VC_ID", 1450026402815676446)
SONGS_FOLDER = "songs"

# --- CHECK FFmpeg ---
if shutil.which("ffmpeg") is None:
    print("Warning: ffmpeg not found in PATH. Voice playback will fail. Install ffmpeg and ensure it is in PATH.")

# --- INIT ---
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
# Do not enable privileged members intent unless you need it
intents.members = False

bot = commands.Bot(command_prefix="!", intents=intents)
voice_client = None
song_list = []
is_playing_song = False
current_song_name = "Nothing"

# --- LOAD SONGS ---
def load_songs():
    global song_list
    song_list.clear()
    if not os.path.isdir(SONGS_FOLDER):
        print(f"Folder {SONGS_FOLDER} missing!")
        return
    for f in os.listdir(SONGS_FOLDER):
        if os.path.splitext(f)[1].lower() in ('.mp3', '.wav', '.flac'):
            song_list.append(os.path.join(SONGS_FOLDER, f))
    print(f"Loaded {len(song_list)} songs.")

# --- PLAYBACK helpers ---
def after_song_finished(error):
    global is_playing_song
    if error:
        print("Error in after_song_finished:", error)
    is_playing_song = False
    # schedule the task in the event loop thread-safely
    bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(play_next_song_start()))

async def play_next_song_start():
    if not play_next_song.is_running():
        play_next_song.start()

@tasks.loop(seconds=1)
async def play_next_song():
    global voice_client, is_playing_song, current_song_name
    # Ensure we have the latest voice client for this guild
    guild = bot.get_guild(GUILD_ID)
    if guild:
        vc = get(bot.voice_clients, guild=guild)
    else:
        vc = None

    # This condition starts a new song if criteria are met (connected, not playing, and songs exist)
    if vc and vc.is_connected() and not vc.is_playing() and song_list and not is_playing_song:
        voice_client = vc
        is_playing_song = True
        song_path = random.choice(song_list)
        current_song_name = os.path.basename(song_path)
        print(f"Now playing: {current_song_name}")
        try:
            # FIX APPLIED: Removed 'before_options' which were causing the FFmpeg error
            source = discord.FFmpegPCMAudio(song_path)
            vc.play(source, after=after_song_finished)
        except Exception as e:
            print(f"Failed to play {current_song_name}: {e}")
            traceback.print_exc()
            is_playing_song = False
            current_song_name = "Nothing"
    # FIX APPLIED: The code block to stop the loop when the song_list is empty has been removed
    # This ensures the loop keeps running indefinitely.

# --- VOICE channel management ---
async def join_channel():
    global voice_client
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            print(f"Bot is not in guild {GUILD_ID} or guild not cached yet.")
            return
        channel = guild.get_channel(VC_ID)
        if channel is None:
            print(f"Voice channel {VC_ID} not found in guild {GUILD_ID}.")
            return

        # Reuse existing voice client if present
        vc = get(bot.voice_clients, guild=guild)
        if vc and vc.is_connected():
            voice_client = vc
            print("Already connected to VC.")
            if song_list and not play_next_song.is_running():
                play_next_song.start()
            return

        voice_client = await channel.connect()
        print("Joined VC.")
        if song_list and not play_next_song.is_running():
            play_next_song.start()
    except Exception as e:
        print("Failed to join voice channel:", e)
        traceback.print_exc()

@tasks.loop(seconds=5)
async def keep_connected():
    guild = bot.get_guild(GUILD_ID)
    vc = get(bot.voice_clients, guild=guild) if guild else None
    if vc is None or not vc.is_connected():
        await join_channel()
    elif vc and vc.is_connected() and song_list and not play_next_song.is_running():
        play_next_song.start()

# --- Status updates ---
@tasks.loop(minutes=10)
async def update_status():
    global current_song_name
    activity = discord.Activity(type=discord.ActivityType.listening, name=current_song_name)
    try:
        await bot.change_presence(activity=activity)
        print(f"Status updated: Listening to {current_song_name}")
    except Exception as e:
        print("Failed to update status:", e)
        traceback.print_exc()

# --- Events ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    load_songs()

    # Ensure command is defined (decorator ran at import time)
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Application commands synced to guild.")
    except Exception as e:
        print("Failed to sync application commands:", e)
        traceback.print_exc()

    # set an initial presence immediately
    try:
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=current_song_name))
    except Exception:
        traceback.print_exc()

    await join_channel()
    keep_connected.start()
    if song_list and not play_next_song.is_running():
        play_next_song.start()
    if not update_status.is_running():
        update_status.start()

@bot.event
async def on_voice_state_update(member, before, after):
    # If the bot was disconnected from the channel, try to rejoin
    if member == bot.user:
        # only trigger when bot's channel changed
        if before.channel and before.channel.id == VC_ID and (after.channel != before.channel):
            print("Bot was moved/disconnected from VC, attempting to rejoin...")
            await join_channel()

# --- Slash commands ---
# Define slash commands at top level so they exist before sync
@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    global voice_client, current_song_name, is_playing_song
    guild = bot.get_guild(GUILD_ID)
    vc = get(bot.voice_clients, guild=guild) if guild else None
    if vc and vc.is_playing():
        song_to_skip = current_song_name
        try:
            vc.stop()
            # reset immediately so status shows nothing while next song loads
            current_song_name = "Nothing"
            is_playing_song = False
            # attempt to start next song immediately
            await play_next_song_start()
            await interaction.response.send_message(f"Skipped: **{song_to_skip}**")
        except Exception as e:
            print("Error while skipping:", e)
            traceback.print_exc()
            await interaction.response.send_message("Failed to skip the song.", ephemeral=True)
    else:
        await interaction.response.send_message("No song is currently playing!", ephemeral=True)

# --- RUN ---
if not TOKEN:
    print("DISCORD_TOKEN missing! Exiting.")
else:
    bot.run(TOKEN)