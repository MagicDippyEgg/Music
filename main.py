import discord
from discord.ext import tasks, commands
import os
import random

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 1386989554682171392))
VC_ID = int(os.getenv("VC_ID", 1450026402815676446))
SONGS_FOLDER = "songs"

# --- INIT ---
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True

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
        if os.path.splitext(f)[1].lower() in ['.mp3', '.wav', '.flac']:
            song_list.append(os.path.join(SONGS_FOLDER, f))
    print(f"Loaded {len(song_list)} songs.")

# --- PLAYBACK ---
def after_song_finished(error):
    global is_playing_song
    is_playing_song = False
    bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(play_next_song_start()))

async def play_next_song_start():
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
        try:
            source = discord.FFmpegPCMAudio(song_path, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5')
            voice_client.play(source, after=after_song_finished)
        except Exception as e:
            print(f"Failed to play {current_song_name}: {e}")
            is_playing_song = False
            current_song_name = "Nothing"
    elif not song_list and play_next_song.is_running():
        print("No songs to play. Stopping loop.")
        play_next_song.stop()
        current_song_name = "Nothing"

# --- VOICE CHANNEL ---
async def join_channel():
    global voice_client
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    channel = guild.get_channel(VC_ID)
    if not channel:
        return
    try:
        if voice_client is None or not voice_client.is_connected():
            voice_client = await channel.connect()
            print("Joined VC.")
            if song_list and not play_next_song.is_running():
                play_next_song.start()
    except Exception as e:
        print("Failed to join VC:", e)

@tasks.loop(seconds=5)
async def keep_connected():
    if voice_client is None or not voice_client.is_connected():
        await join_channel()
    elif voice_client and voice_client.is_connected() and song_list and not play_next_song.is_running():
        play_next_song.start()

# --- STATUS ---
@tasks.loop(minutes=10)
async def update_status():
    global current_song_name
    activity = discord.Activity(type=discord.ActivityType.listening, name=current_song_name)
    await bot.change_presence(activity=activity)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    load_songs()

    # Sync slash commands to guild
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Commands synced.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

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
                print("Disconnected from VC! Rejoining...")
                await join_channel()

# --- SLASH COMMANDS ---
@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    global voice_client, current_song_name
    if voice_client and voice_client.is_playing():
        song_to_skip = current_song_name
        voice_client.stop()
        current_song_name = "Nothing"
        await interaction.response.send_message(f"Skipped: **{song_to_skip}**")
    else:
        await interaction.response.send_message("No song is currently playing!", ephemeral=True)

# --- RUN ---
if not TOKEN:
    print("DISCORD_TOKEN missing!")
else:
    bot.run(TOKEN)
