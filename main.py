import os
import yt_dlp
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from concurrent.futures import ThreadPoolExecutor
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch

# Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Spotify API credentials (fill with your values)
SPOTIFY_CLIENT_ID = "22b6125bfe224587b722d6815002db2b"
SPOTIFY_CLIENT_SECRET = "c9c63c6fbf2f467c8bc68624851e9773"

# Initialize Spotify client
spotify = Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID,
                                                      client_secret=SPOTIFY_CLIENT_SECRET))

# JioSaavn API endpoint
SAAVN_API = "https://saavn.dev/api/search/songs"

# Setup Pyrogram client
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

executor = ThreadPoolExecutor(max_workers=2)

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'concurrent_fragment_downloads': 4,
}

# Search JioSaavn songs
async def search_songs(query):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params={"query": query, "limit": 1}) as resp:
                data = await resp.json()
                return data['data']['results'] if data.get('success') else None
        except Exception as e:
            print(f"Search error: {e}")
            return None

# Search Spotify track
def search_spotify_track(query):
    try:
        results = spotify.search(q=query, type='track', limit=1)
        tracks = results.get('tracks', {}).get('items', [])
        if not tracks:
            return None
        track = tracks[0]
        track_name = track['name']
        artists = ", ".join([artist['name'] for artist in track['artists']])
        return f"{track_name} {artists}"
    except Exception as e:
        print(f"Spotify search error: {e}")
        return None

# Synchronous YouTube search (to run in executor)
def search_youtube(query):
    videos_search = VideosSearch(query, limit=1)
    result = videos_search.result()
    if result and result.get('result'):
        return result['result'][0]['link']
    return None

# Download song using yt-dlp
async def download_song(url):
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await loop.run_in_executor(executor, extract)
    return info.get('title', 'song'), info.get('artist', 'Unknown'), int(info.get('duration', 0))

# Download & send audio to Telegram
async def process_and_send(chat_id, url, status_msg):
    try:
        title, artist, duration = await download_song(url)
        file_name = f"{title}.mp3"

        if os.path.exists(file_name):
            await status_msg.edit_text("📤 Uploading...")
            await app.send_audio(
                chat_id,
                audio=file_name,
                title=title,
                performer=artist,
                duration=duration,
            )
            await status_msg.delete()
            await asyncio.get_event_loop().run_in_executor(executor, os.remove, file_name)
        else:
            await status_msg.edit_text("❌ Downloaded file not found.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("Send JioSaavn or Spotify link, or song name.")

@app.on_message(filters.command("help"))
async def help(client, message: Message):
    await message.reply_text("Send JioSaavn/Spotify song link or name. I'll download & send it.")

@app.on_message(filters.text & non_command_filter)
async def handle_text(client, message: Message):
    text = message.text.strip()
    status_msg = await message.reply("🔍 Processing...")

    if "jiosaavn.com" in text:
        await process_and_send(message.chat.id, text, status_msg)
        return

    if "spotify.com" in text:
        try:
            track_id = text.split("track/")[1].split("?")[0]
            track_info = spotify.track(track_id)
            query = f"{track_info['name']} {' '.join([a['name'] for a in track_info['artists']])}"
        except Exception:
            await status_msg.edit_text("❌ Invalid Spotify track URL.")
            return
    else:
        query = search_spotify_track(text)
        if query is None:
            query = text

    # Run blocking YouTube search in executor
    loop = asyncio.get_event_loop()
    yt_url = await loop.run_in_executor(None, search_youtube, query)

    if not yt_url:
        await status_msg.edit_text("❌ No matching YouTube video found.")
        return

    await process_and_send(message.chat.id, yt_url, status_msg)

if __name__ == "__main__":
    print("✅ Bot starting with Spotify support...")
    app.run()
