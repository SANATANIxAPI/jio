from pyrogram import Client, filters
from pyrogram.types import Message
import aiohttp
import os
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

# Search function for Saavn API
async def search_songs(query):
    SAAVN_API = "https://saavn.dev/api/search/songs"
    params = {'query': query, 'limit': 1}
    headers = {'User-Agent': 'Mozilla/5.0'}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params=params, headers=headers) as response:
                data = await response.json()
                if data.get('success') and data['data'].get('results'):
                    results = data['data']['results']
                    for r in results:
                        if 'downloadUrl' in r and isinstance(r['downloadUrl'], list):
                            r['downloadUrl'] = r['downloadUrl'][-1]['link']
                    return results
        except Exception as e:
            print(f"Search error: {e}")
    return None

async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(filename, 'wb') as f:
                    while True:
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return filename
    return None

async def send_song(chat_id, result, status_msg):
    title = result.get("name", "Unknown Title")
    artist = result.get("primaryArtists", "Unknown Artist")
    duration = int(result.get("duration", 0))
    download_link = result.get("downloadUrl")

    filename = f"{title}.mp3"
    await status_msg.edit_text("🔽 Downloading...")

    file_path = await download_file(download_link, filename)
    if not file_path:
        await status_msg.edit_text("❌ Failed to download audio.")
        return

    await status_msg.edit_text("📤 Uploading...")
    await app.send_audio(
        chat_id=chat_id,
        audio=file_path,
        title=title,
        performer=artist,
        duration=duration
    )
    await status_msg.delete()

    try:
        os.remove(file_path)
    except:
        pass

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hello! Send me a JioSaavn URL or a song name, and I’ll fetch and send the audio to you."
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "🎵 Usage:\n"
        "- Send a **JioSaavn URL** or\n"
        "- Send just the **song name**.\n\n"
        "Example:\n"
        "`https://www.jiosaavn.com/song/let-me-love-you/KD8zfRtiYms`\n"
        "`Let Me Love You`",
        parse_mode=None
    )

# Custom filter to exclude commands
def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.text & non_command_filter)
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    status_msg = await message.reply_text("⏳ Processing your request...")

    if "jiosaavn.com" in text:
        results = await search_songs(text)
    else:
        results = await search_songs(text)

    if not results:
        await status_msg.edit_text("❌ No song found.")
        return

    await send_song(message.chat.id, results[0], status_msg)

if __name__ == "__main__":
    print("✅ Bot is starting...")
    app.run()
