=== Dockerfile ===
# Use Python 3.10 slim image (Lightweight)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (FFmpeg is REQUIRED for audio)
# libffi-dev and libnacl-dev are needed for Discord Voice
RUN apt-get update && \
    apt-get install -y ffmpeg libffi-dev libnacl-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*
# test
# Copy requirements first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application (including songs folder)
COPY . .

# Run the bot
CMD ["python", "main.py"]

=== requirements.txt ===
discord.py>=2.3.0
PyNaCl>=1.5.0  # Required for Voice
asyncio
# pyttsx3 removed (requires heavy system libs, causes crashes on minimal hosts)

=== main.py (secure) ===
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

# ... (Copy the rest of your logic functions here: play_next_song, join_channel) ...

# Check if TOKEN exists before running
if not TOKEN:
    print("Error: DISCORD_TOKEN not found in environment variables.")
else:
    client.run(TOKEN)