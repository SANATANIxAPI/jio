import os
import yt_dlp
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineQuery, InlineQueryResultAudio
from concurrent.futures import ThreadPoolExecutor
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from time import time

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
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
    'concurrent_fragment_downloads': 4,
}

async def search_songs(query):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params={"query": query, "limit": 1}) as resp:
                data = await resp.json()
                return data['data']['results'] if data.get('success') else None
        except Exception as e:
            print(f"Search error: {e}")
            return None

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

def search_youtube(query):
    ydl_search_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'default_search': 'ytsearch1',
    }
    with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info and info['entries']:
            return info['entries'][0]['url']
    return None

async def download_song(url):
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await loop.run_in_executor(executor, extract)
    title = info.get('title', 'song')
    artist = info.get('artist', 'Unknown')
    duration = int(info.get('duration', 0))
    filename = f"{title}.mp3"
    return title, artist, duration, filename

async def process_and_send(chat_id, url, status_msg):
    if url in cache and os.path.exists(cache[url]):
        await status_msg.edit_text("\ud83d\udce4 Uploading from cache...")
        await app.send_audio(chat_id, audio=cache[url])
        await status_msg.delete()
        return

    try:
        title, artist, duration, filename = await download_song(url)
        if os.path.exists(filename):
            cache[url] = filename
            stats["downloads"] += 1
            await status_msg.edit_text("\ud83d\udce4 Uploading...")
            await app.send_audio(
                chat_id,
                audio=filename,
                title=title,
                performer=artist,
                duration=duration,
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("\u274c Downloaded file not found.")
    except Exception as e:
        await status_msg.edit_text(f"\u274c Error: {str(e)}")

async def handle_queue(chat_id):
    if chat_id not in queues or not queues[chat_id]:
        return

    url, status_msg = queues[chat_id].pop(0)
    await process_and_send(chat_id, url, status_msg)
    if queues[chat_id]:
        await handle_queue(chat_id)

def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("\ud83c\udfb5 \u0917\u093e\u0928\u093e \u092d\u0947\u091c\u093f\u090f \u092f\u093e JioSaavn/Spotify \u0932\u093f\u0902\u0915 \u0926\u0940\u091c\u093f\u090f\u0964")

@app.on_message(filters.command("help"))
async def help(client, message: Message):
    await message.reply_text("\u0907\u0938 \u092c\u0949\u091f \u0938\u0947 \u0906\u092a JioSaavn \u092f\u093e Spotify \u0917\u093e\u0928\u0947 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0915\u0930 \u0938\u0915\u0924\u0947 \u0939\u0948\u0902\u0964")

@app.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    uptime = int(time() - stats["start_time"])
    await message.reply_text(
        f"\ud83d\udcca Stats:\n\ud83d\udc64 Users: {message.chat.id}\n\ud83c\udfb6 Downloads: {stats['downloads']}\n\u23f1\ufe0f Uptime: {uptime // 60} minutes"
    )

@app.on_message(filters.text & non_command_filter)
async def handle_text(client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id
    status_msg = await message.reply("\ud83d\udd0d Processing...")

    if "jiosaavn.com" in text:
        url = text
    elif "spotify.com" in text:
        try:
            track_id = text.split("track/")[1].split("?")[0]
            track_info = spotify.track(track_id)
            query = f"{track_info['name']} {' '.join([a['name'] for a in track_info['artists']])}"
            url = search_youtube(query)
        except Exception:
            await status_msg.edit_text("\u274c Invalid Spotify track URL.")
            return
    else:
        query = search_spotify_track(text) or text
        url = search_youtube(query)

    if not url:
        await status_msg.edit_text("\u274c \u0915\u094b\u0908 YouTube \u0935\u0940\u0921\u093f\u092f\u094b \u0928\u0939\u0940\u0902 \u092e\u093f\u0932\u093e\u0964")
        return

    if chat_id not in queues:
        queues[chat_id] = []
    queues[chat_id].append((url, status_msg))
    if len(queues[chat_id]) == 1:
        await handle_queue(chat_id)
    else:
        await status_msg.edit_text(f"\u23f3 \u0915\u0924\u093e\u0930 \u092e\u0947\u0902 \u0939\u0948, \u0938\u094d\u0925\u093f\u0924\u093f: {len(queues[chat_id])}")

@app.on_inline_query()
async def inline_query_handler(client: Client, inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer([], cache_time=1)
        return

    try:
        ydl_search_opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': 'in_playlist',
            'default_search': 'ytsearch5',
        }
        with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = info.get("entries", [])

        answers = []
        for video in results:
            title = video.get("title")
            link = f"https://youtube.com/watch?v={video.get('id')}"
            channel = video.get("uploader", "Unknown")
            answers.append(
                InlineQueryResultAudio(
                    title=title,
                    performer=channel,
                    audio_url=link,
                    caption=f"\ud83c\udfb5 {title} — {channel}\n{link}",
                    input_message_content=None
                )
            )
        await inline_query.answer(answers, cache_time=0)
    except Exception as e:
        print("Inline search error:", e)
        await inline_query.answer([], cache_time=1)

if __name__ == "__main__":
    print("\u2705 \u092c\u0949\u091f \u091a\u093e\u0932\u0942 \u0939\u094b \u0917\u092f\u093e \u0939\u0948...")
    app.run()
