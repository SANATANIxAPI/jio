import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from concurrent.futures import ThreadPoolExecutor
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from time import time
import yt_dlp
import requests  # Added for better JioSaavn API handling

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

# JioSaavn API endpoints
SAAVN_SEARCH_API = "https://www.jiosaavn.com/api.php"
SAAVN_SONG_API = "https://www.jiosaavn.com/api.php"

# Setup Pyrogram client
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins")  # This helps with TgCrypto warning

executor = ThreadPoolExecutor(max_workers=4)  # Increased workers

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
    'extract_flat': True,
}

async def search_saavn_songs(query):
    params = {
        '__call': 'search.getResults',
        'p': 1,
        'q': query,
        'n': 1,
        '_format': 'json',
        'ctx': 'web6dot0'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(SAAVN_SEARCH_API, params=params) as resp:
                data = await resp.json()
                if data and 'results' in data and data['results']:
                    song = data['results'][0]
                    return {
                        'url': f"https://www.jiosaavn.com/song/{song.get('perma_url', '').split('/')[-1]}",
                        'title': song.get('title', 'Unknown'),
                        'artist': song.get('singers', 'Unknown'),
                        'duration': int(song.get('duration', 0))
                    }
                return None
    except Exception as e:
        print(f"JioSaavn search error: {e}")
        return None

async def get_saavn_song(url):
    song_id = url.split('/')[-1].split('?')[0]
    params = {
        '__call': 'song.getDetails',
        'cc': 'in',
        'p': 1,
        '_format': 'json',
        'mark': 1,
        'ctx': 'web6dot0',
        'network': '4g',
        'network_subtype': 'unknown',
        'network_type': 'unknown',
        'api_version': '4',
        '_marker': 0,
        'token': song_id
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(SAAVN_SONG_API, params=params) as resp:
                data = await resp.json()
                if data and 'songs' in data and data['songs']:
                    song = data['songs'][0]
                    return {
                        'title': song.get('song', 'Unknown'),
                        'artist': song.get('primary_artists', 'Unknown'),
                        'duration': int(song.get('duration', 0)),
                        'download_url': song.get('media_url', '')
                    }
                return None
    except Exception as e:
        print(f"JioSaavn song fetch error: {e}")
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
        track_info = spotify.track(url.split('track/')[1].split('?')[0])
        query = f"{track_info['name']} {', '.join([a['name'] for a in track_info['artists']])}"
        song_info = await search_saavn_songs(query)
        if not song_info:
            return None
        url = song_info['url']
    
    # Check if it's a JioSaavn URL
    if 'jiosaavn.com' in url:
        song_info = await get_saavn_song(url)
        if not song_info:
            return None
        
        # Download the song directly from JioSaavn
        def download():
            try:
                download_url = song_info['download_url'].replace('_96.mp4', '_320.mp4')
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(download_url, download=True)
            except Exception as e:
                print(f"Download error: {e}")
                return None
        
        info = await loop.run_in_executor(executor, download)
        if not info:
            return None
            
        title = song_info['title']
        artist = song_info['artist']
        duration = song_info['duration']
        filename = f"{title}.mp3"
        return title, artist, duration, filename
    
    return None

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
                title=title[:64],  # Telegram has title length limit
                performer=artist[:64],
                duration=duration,
            )
            await status_msg.delete()
            # Clean up after sending
            try:
                os.remove(filename)
            except:
                pass
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
    help_text = """
**How to use this bot:**
- Send a JioSaavn song link
- Send a Spotify song link
- Or search for a song by name

The bot will search JioSaavn for the song and send it to you.
"""
    await message.reply_text(help_text)

@app.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    uptime = int(time() - stats["start_time"])
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    stats_text = f"""
📊 **Bot Stats:**
👤 Users: {message.chat.id}
🎶 Total Downloads: {stats['downloads']}
⏱ Uptime: {hours}h {minutes}m {seconds}s
"""
    await message.reply_text(stats_text)

@app.on_message(filters.text & non_command_filter)
async def handle_text(client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id
    status_msg = await message.reply("🔍 Processing...")

    is_spotify = False
    
    if "jiosaavn.com" in text or "saavn.com" in text:
        url = text
    elif "spotify.com" in text and "track" in text:
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

# Install TgCrypto if available
try:
    import TgCrypto
    print("✅ TgCrypto found - running at full speed!")
except ImportError:
    print("ℹ️ TgCrypto not found - running at normal speed")

if __name__ == "__main__":
    print("✅ Bot started...")
    app.run()
