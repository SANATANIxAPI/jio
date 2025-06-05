from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
import os
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Telegram Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Initialize the Pyrogram Client
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

executor = ThreadPoolExecutor(max_workers=2)

# yt-dlp options for downloading audio
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

SAAVN_API = "https://saavn.dev/api/search/songs"

async def search_songs(query):
    params = {'query': query, 'limit': 1}
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params=params, headers=headers) as resp:
                data = await resp.json()
                if data.get('success') and data.get('data', {}).get('results'):
                    return data['data']['results']
                return None
        except Exception as e:
            print(f"Saavn search error: {e}")
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
    return title, artist, duration

async def process_and_send(chat_id, url, status_msg):
    try:
        title, artist, duration = await download_song(url)
        file_name = f"{title}.mp3"

        if os.path.exists(file_name):
            await status_msg.edit_text("Uploading audio...")
            await app.send_audio(
                chat_id=chat_id,
                audio=file_name,
                title=title,
                performer=artist,
                duration=duration,
                disable_notification=True
            )
            await status_msg.delete()
            await asyncio.get_event_loop().run_in_executor(executor, os.remove, file_name)
        else:
            await status_msg.edit_text("❌ Error: Downloaded file not found!")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

async def youtube_search_and_download(query, chat_id, status_msg):
    loop = asyncio.get_event_loop()
    def yt_search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch1:{query}", download=False)
    try:
        info = await loop.run_in_executor(executor, yt_search)
        video = info['entries'][0]
        url = video['webpage_url']
        await process_and_send(chat_id, url, status_msg)
    except Exception as e:
        await status_msg.edit_text(f"YouTube search error: {e}")

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hello! Send me a JioSaavn or YouTube URL or a song name, "
        "and I'll download and send the song directly."
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a JioSaavn or YouTube URL directly\n"
        "2. Or send a song name, I'll search JioSaavn and fallback to YouTube\n\n"
        "Example JioSaavn URL:\n"
        "https://www.jiosaavn.com/song/let-me-love-you/KD8zfRtiYms\n"
        "Example YouTube URL:\n"
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
        "Example search:\n"
        "Let Me Love You"
    )

def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.text & non_command_filter)
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    status_msg = await message.reply_text("Processing your request...")

    # Check if JioSaavn URL
    if "jiosaavn.com" in text:
        await process_and_send(message.chat.id, text, status_msg)
        return

    # Check if YouTube URL
    if "youtube.com" in text or "youtu.be" in text:
        await process_and_send(message.chat.id, text, status_msg)
        return

    # Search on Saavn first
    results = await search_songs(text)
    if results:
        first_song_url = results[0]['url']
        await process_and_send(message.chat.id, first_song_url, status_msg)
        return

    # Fallback to YouTube search
    await youtube_search_and_download(text, message.chat.id, status_msg)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
