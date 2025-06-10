import os
import yt_dlp
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineQuery, InlineQueryResultAudio
from concurrent.futures import ThreadPoolExecutor
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch
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
    videos_search = VideosSearch(query, limit=1)
    result = videos_search.result()
    if result and result.get('result'):
        return result['result'][0]['link']
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
        await status_msg.edit_text("📤 Uploading from cache...")
        await app.send_audio(chat_id, audio=cache[url])
        await status_msg.delete()
        return

    try:
        title, artist, duration, filename = await download_song(url)
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

    url, status_msg = queues[chat_id].pop(0)
    await process_and_send(chat_id, url, status_msg)
    if queues[chat_id]:
        await handle_queue(chat_id)

def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("🎵 गाना भेजिए या JioSaavn/Spotify लिंक दीजिए।")

@app.on_message(filters.command("help"))
async def help(client, message: Message):
    await message.reply_text("इस बॉट से आप JioSaavn या Spotify गाने डाउनलोड कर सकते हैं।")

@app.on_message(filters.command("stats"))
async def show_stats(client, message: Message):
    uptime = int(time() - stats["start_time"])
    await message.reply_text(
        f"📊 Stats:\n👤 Users: {message.chat.id}\n🎶 Downloads: {stats['downloads']}\n⏱️ Uptime: {uptime // 60} minutes"
    )

@app.on_message(filters.text & non_command_filter)
async def handle_text(client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id
    status_msg = await message.reply("🔍 Processing...")

    if "jiosaavn.com" in text:
        url = text
    elif "spotify.com" in text:
        try:
            track_id = text.split("track/")[1].split("?")[0]
            track_info = spotify.track(track_id)
            query = f"{track_info['name']} {' '.join([a['name'] for a in track_info['artists']])}"
            url = search_youtube(query)
        except Exception:
            await status_msg.edit_text("❌ Invalid Spotify track URL.")
            return
    else:
        query = search_spotify_track(text) or text
        url = search_youtube(query)

    if not url:
        await status_msg.edit_text("❌ कोई YouTube वीडियो नहीं मिला।")
        return

    if chat_id not in queues:
        queues[chat_id] = []
    queues[chat_id].append((url, status_msg))
    if len(queues[chat_id]) == 1:
        await handle_queue(chat_id)
    else:
        await status_msg.edit_text(f"⏳ कतार में है, स्थिति: {len(queues[chat_id])}")

@app.on_inline_query()
async def inline_query_handler(client: Client, inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer([], cache_time=1)
        return

    try:
        results = VideosSearch(query, limit=5).result().get("result", [])
        answers = []
        for video in results:
            title = video["title"]
            link = video["link"]
            channel = video["channel"]["name"]
            answers.append(
                InlineQueryResultAudio(
                    title=title,
                    performer=channel,
                    audio_url=link,
                    caption=f"🎵 {title} — {channel}\n{link}",
                    input_message_content=None
                )
            )
        await inline_query.answer(answers, cache_time=0)
    except Exception as e:
        print("Inline search error:", e)
        await inline_query.answer([], cache_time=1)

if __name__ == "__main__":
    print("✅ बॉट चालू हो गया है...")
    app.run()
