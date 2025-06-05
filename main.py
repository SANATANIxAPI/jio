from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import os
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

# Telegram Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Initialize the Pyrogram Client
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Thread pool for faster I/O operations
executor = ThreadPoolExecutor(max_workers=2)

# In-memory storage for URL mapping
url_map = {}

# yt-dlp configuration
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
        'limit': 10  # Limit to 3 results
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params=params, headers=headers) as response:
                data = await response.json()
                print(f"API Response: {data}")  # Debug output
                if data.get('success') and data.get('data', {}).get('results'):
                    return data['data']['results']
                return None
        except Exception as e:
            print(f"Search error: {e}")
            return None

async def download_song(url):
    """Download song in a separate thread"""
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = await loop.run_in_executor(executor, lambda: ydl.extract_info(url, download=True))
        return info.get('title', 'song'), info.get('artist', 'Unknown'), int(info.get('duration', 0))

async def process_and_send(chat_id, url, status_msg):
    """Process and send song efficiently"""
    try:
        title, artist, duration = await download_song(url)
        file_name = f"{title}.mp3"

        if os.path.exists(file_name):
            await status_msg.edit_text("Uploading...")
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
            await status_msg.edit_text("Error: File not found after download!")
    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")

# Start command
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hello! I'm a JioSaavn downloader bot.\n"
        "Send a JioSaavn URL or song name!"
    )

# Handler for text messages
@app.on_message(filters.text)
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    status_msg = await message.reply_text("Processing...")

    # Check if it's a URL
    if "jiosaavn.com" in text:
        await process_and_send(message.chat.id, text, status_msg)
        return

    # Search for song
    results = await search_songs(text)
    if not results or not isinstance(results, list) or len(results) == 0:
        await status_msg.edit_text("No results found! Try a different song name.")
        return

    # Generate short IDs and store URLs
    keyboard = []
    for song in results:
        short_id = str(uuid.uuid4())[:8]  # Short unique ID (8 chars)
        url_map[short_id] = song['url']
        keyboard.append([InlineKeyboardButton(
            f"{song['name']} - {song.get('primaryArtists', 'Unknown')}",
            callback_data=f"dl:{short_id}"
        )])
    
    await status_msg.edit_text(
        "Select a song:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Callback handler
@app.on_callback_query(filters.regex(r"^dl:"))
async def callback_handler(client: Client, callback_query):
    short_id = callback_query.data.split("dl:")[1]
    url = url_map.get(short_id)
    if not url:
        await callback_query.answer("Error: Song URL not found!", show_alert=True)
        return
    
    await callback_query.answer()
    status_msg = await callback_query.message.edit_text("Processing...")
    await process_and_send(callback_query.message.chat.id, url, status_msg)
    # Clean up
    url_map.pop(short_id, None)

# Help command
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a JioSaavn URL\n"
        "2. Or type a song name to search\n"
        "Example URL: https://www.jiosaavn.com/song/let-me-love-you/KD8zfRtiYms\n"
        "Example search: Let Me Love You"
    )

# Run the bot
if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
