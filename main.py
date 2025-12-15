import discord
from discord.ext import tasks
import asyncio
import os
import random

# --- SECURE CONFIGURATION ---
# Use os.getenv to read from the cloud platform settings
# DO NOT hardcode the token here
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 1386989554682171392))
VC_ID = int(os.getenv("VC_ID", 1450026402815676446))
SONGS_FOLDER = "songs"

# --- Initialization ---
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True

client = discord.Client(intents=intents)
voice_client = None
song_list = []
is_playing_song = False

def load_songs():
    # ... (Same as your code) ...
    global song_list
    if not os.path.isdir(SONGS_FOLDER):
        print(f"Folder {SONGS_FOLDER} missing!")
        return
    
    valid_extensions = ['.mp3', '.wav', '.flac']
    for filename in os.listdir(SONGS_FOLDER):
        ext = os.path.splitext(filename)[1].lower()
        if ext in valid_extensions:
            song_list.append(os.path.join(SONGS_FOLDER, filename))
    print(f"Found {len(song_list)} songs.")

def after_song_finished(error):
    global is_playing_song
    is_playing_song = False
    if not play_next_song.is_running():
        play_next_song.start()

@tasks.loop(seconds=1) # Check frequently to start the next song
async def play_next_song():
    global voice_client, is_playing_song

    # Only proceed if the bot is connected, not currently playing, and has songs
    if voice_client and voice_client.is_connected() and not voice_client.is_playing() and song_list and not is_playing_song:
        is_playing_song = True
        
        song_path = random.choice(song_list)
        print(f"Now playing: {os.path.basename(song_path)}")

        try:
            source = discord.FFmpegPCMAudio(song_path)
            # The 'after' callback ensures the next song starts when this one finishes
            voice_client.play(source, after=after_song_finished)
        except Exception as e:
            print(f"Failed to play song {song_path}: {e}")
            is_playing_song = False # Reset flag on failure

    elif not song_list and play_next_song.is_running():
        print("No songs to play. Stopping music loop.")
        play_next_song.stop()

# --- Voice Channel Functions ---

async def join_channel():
    global voice_client
    guild = client.get_guild(GUILD_ID)
    if guild:
        channel = guild.get_channel(VC_ID)
        if channel:
            try:
                if voice_client is None or not voice_client.is_connected():
                    voice_client = await channel.connect()
                    print("Joined voice channel.")
                    
                    # Start the music loop when the bot successfully joins
                    if song_list and not play_next_song.is_running():
                        play_next_song.start()
                        
            except Exception as e:
                print("Failed to join:", e)

@tasks.loop(seconds=5)
async def keep_connected():
    # Only try to join if the bot is not already connected
    if voice_client is None or not voice_client.is_connected():
        await join_channel()
    # Ensure music loop is running if connected and there are songs
    elif voice_client and voice_client.is_connected() and song_list and not play_next_song.is_running():
        play_next_song.start()


# --- Events ---

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    load_songs() # Load songs once on startup
    await join_channel()
    keep_connected.start()
    
    # Start the music player right after joining
    if song_list and not play_next_song.is_running():
        play_next_song.start()

@client.event
async def on_voice_state_update(member, before, after):
    global voice_client
    # If the bot itself disconnects, try to rejoin and restart music
    if member == client.user:
        if before.channel and before.channel.id == VC_ID:
            if after.channel != before.channel:
                print("Disconnected! Rejoining...")
                await join_channel()

# Removed all logic related to welcoming other members

if not TOKEN:
    print("Error: DISCORD_TOKEN not found in environment variables.")
else:
    client.run(TOKEN)