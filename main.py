import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineQuery, InlineQueryResultAudio
from concurrent.futures import ThreadPoolExecutor
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from time import time
import yt_dlp

# Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Spotify API credentials
SPOTIFY_CLIENT_ID = "22b6125bfe224587b722d6815002db2b"
SPOTIFY_CLIENT_SECRET = "c9c63c6fbf2f467c8bc68624851e9773"

# Initialize Spotify client
spotify = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET))

# JioSaavn API endpoint
SAAVN_API = "https://saavn.dev/api/search/songs"

# Setup Pyrogram client
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

executor = ThreadPoolExecutor(max_workers=2)

# Cache and stats
cache = {}  # {url: filename}
stats = {"downloads": 0, "start_time": time()}

# Chat-wise download queues
queues = {}  # {chat_id: [url1, url2, ...]}

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
}

async def search_saavn_songs(query):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params={"query": query, "limit": 1}) as resp:
                data = await resp.json()
                if data.get('success'):
                    song = data['data']['results'][0]
                    return {
                        'url': song['url'],
                        'title': song['name'],
                        'artist': ', '.join(song['primaryArtists'].split('~')),
                        'duration': song['duration']
                    }
                return None
        except Exception as e:
            print(f"JioSaavn search error: {e}")
            return None

def search_spotify_track(query):
    try:
        results = spotify.search(q=query, type='track', limit=1)
        tracks = results.get('tracks', {}).get('items', [])
        if not tracks:
            return None
        track = tracks[0]
        return {
            'title': track['name'],
            'artist': ', '.join([artist['name'] for artist in track['artists']]),
            'duration': track['duration_ms'] // 1000,
            'url': track['external_urls']['spotify']
        }
    except Exception as e:
        print(f"Spotify search error: {e}")
        return None

async def download_from_url(url, is_spotify=False):
    loop = asyncio.get_event_loop()
    
    if is_spotify:
        # For Spotify, we need to search JioSaavn first
        track_info = spotify.track(url.split('track/')[1].split('?')[0])
        query = f"{track_info['name']} {', '.join([a['name'] for a in track_info['artists']])}"
        song_info = await search_saavn_songs(query)
        if not song_info:
            return None
        url = song_info['url']
    
    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)
    
    info = await loop.run_in_executor(executor, download)
    title = info.get('title', 'song')
    artist = info.get('artist', 'Unknown')
    duration = int(info.get('duration', 0))
    filename = f"{title}.mp3"
    return title, artist, duration, filename

async def process_and_send(chat_id, url, status_msg, is_spotify=False):
    if url in cache and os.path.exists(cache[url]):
        await status_msg.edit_text("📤 Uploading from cache...")
        await app.send_audio(chat_id, audio=cache[url])
        await status_msg.delete()
        return

    try:
        result = await download_from_url(url, is_spotify)
        if not result:
            await status_msg.edit_text("❌ Song not found on JioSaavn")
            return
            
        title, artist, duration, filename = result
        if os.path.exists(filename):
            cache[url] = filename
            stats["downloads"] += 1
            await status_msg.edit_text("📤 Uploading...")
            await app.send_audio(
                chat_id,
                audio=filename,
                title=title,
                performer=artist,
                duration=duration,
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Downloaded file not found.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_queue(chat_id):
    if chat_id not in queues or not queues[chat_id]:
        return

    url, status_msg, is_spotify = queues[chat_id].pop(0)
    await process_and_send(chat_id, url, status_msg, is_spotify)
    if queues[chat_id]:
        await handle_queue(chat_id)

def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("🎵 Send me a JioSaavn or Spotify song link or search query")

@app.on_message(filters.command("help"))
async def help(client, message: Message):
    await message.reply_text("Just send me:\n- A JioSaavn song link\n- A Spotify song link\n- Or search for a song")

@app.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    uptime = int(time() - stats["start_time"])
    await message.reply_text(
        f"📊 Stats:\n👤 Users: {message.chat.id}\n🎶 Downloads: {stats['downloads']}\n⏱ Uptime: {uptime // 60} minutes"
    )

@app.on_message(filters.text & non_command_filter)
async def handle_text(client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id
    status_msg = await message.reply("🔍 Processing...")

    is_spotify = False
    
    if "jiosaavn.com" in text or "saavn.com" in text:
        url = text
    elif "spotify.com" in text:
        is_spotify = True
        url = text
    else:
        # Search JioSaavn for the query
        song_info = await search_saavn_songs(text)
        if not song_info:
            await status_msg.edit_text("❌ Song not found on JioSaavn")
            return
        url = song_info['url']

    if chat_id not in queues:
        queues[chat_id] = []
    queues[chat_id].append((url, status_msg, is_spotify))
    if len(queues[chat_id]) == 1:
        await handle_queue(chat_id)
    else:
        await status_msg.edit_text(f"⌛ In queue, position: {len(queues[chat_id])}")

if __name__ == "__main__":
    print("✅ Bot started...")
    app.run()
