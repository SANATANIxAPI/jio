from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
import asyncio
import re

API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

app = Client("direct_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def is_url(text):
    return bool(re.match(r'https?://', text))

def get_direct_audio_link(query_or_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'default_search': 'auto',  # if not URL, treat as search
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query_or_url, download=False)
        # If search result, take first entry
        if 'entries' in info:
            info = info['entries'][0]

        for f in info.get('formats', []):
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('url'), info.get('title')
        # fallback to info url
        return info.get('url'), info.get('title')

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Send me a YouTube or JioSaavn URL or a song name,\n"
        "and I will provide you the direct audio download link without downloading the file!"
    )

@app.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a direct YouTube/JioSaavn URL\n"
        "2. Or send a song name to search YouTube automatically\n"
        "3. You'll get a direct audio stream/download link."
    )

@app.on_message(filters.text & ~filters.command(commands=["start", "help"]))
async def handle_message(client, message: Message):
    query_or_url = message.text.strip()
    status = await message.reply_text("Generating direct download link...")

    loop = asyncio.get_event_loop()

    def extract_link():
        try:
            return get_direct_audio_link(query_or_url)
        except Exception as e:
            return None, str(e)

    direct_url, title_or_error = await loop.run_in_executor(None, extract_link)

    if direct_url:
        await status.edit_text(
            f"🎵 *{title_or_error}*\n\nHere is your direct audio download link:\n{direct_url}",
            parse_mode="md"
        )
    else:
        await status.edit_text(f"❌ Error: {title_or_error}")

if __name__ == "__main__":
    print("Bot started...")
    app.run()
