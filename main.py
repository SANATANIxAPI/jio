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

# Thread pool for blocking I/O operations
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

# Saavn.dev API endpoint
SAAVN_API = "https://saavn.dev/api/search/songs"

async def search_songs(query):
    """Search songs using saavn.dev API"""
    params = {
        'query': query,
        'limit': 1  # Only need the top result
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params=params, headers=headers) as response:
                data = await response.json()
                if data.get('success') and data.get('data', {}).get('results'):
                    return data['data']['results']
                return None
        except Exception as e:
            print(f"Search error: {e}")
            return None

async def download_song(url):
    """Download song using yt-dlp in thread executor"""
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
    """Download and send audio file"""
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
            # Remove file after sending
            await asyncio.get_event_loop().run_in_executor(executor, os.remove, file_name)
        else:
            await status_msg.edit_text("❌ Error: Downloaded file not found!")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hello! Send me a JioSaavn URL or a song name, and I'll download and send the song directly."
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a JioSaavn URL directly\n"
        "2. Or send a song name, I'll search and download the first result\n\n"
        "Example URL: https://www.jiosaavn.com/song/let-me-love-you/KD8zfRtiYms\n"
        "Example search: Let Me Love You"
    )

@app.on_message(filters.text & ~filters.command())
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    status_msg = await message.reply_text("Processing your request...")

    if "jiosaavn.com" in text:
        # Direct URL given, download & send
        await process_and_send(message.chat.id, text, status_msg)
        return

    # Treat input as song name, search and download first result
    results = await search_songs(text)
    if not results:
        await status_msg.edit_text("No results found for your query!")
        return

    first_song_url = results[0]['url']
    await process_and_send(message.chat.id, first_song_url, status_msg)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
