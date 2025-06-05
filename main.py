from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
import asyncio

API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

app = Client("direct_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_direct_audio_link(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # Try to find best audio-only format URL
        for f in info.get('formats', []):
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('url'), info.get('title')
        # fallback to general url
        return info.get('url'), info.get('title')

@app.on_message(filters.text & ~filters.command)
async def handle_message(client, message: Message):
    url_or_query = message.text.strip()
    status = await message.reply_text("Generating direct download link...")

    loop = asyncio.get_event_loop()

    def extract_link():
        try:
            return get_direct_audio_link(url_or_query)
        except Exception as e:
            return None, str(e)

    direct_url, title_or_error = await loop.run_in_executor(None, extract_link)

    if direct_url:
        await status.edit_text(f"🎵 *{title_or_error}*\n\nHere is your direct audio download link:\n{direct_url}", parse_mode="markdown")
    else:
        await status.edit_text(f"❌ Error: {title_or_error}")

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Send me a JioSaavn or YouTube URL (or search query) and I will give you the direct audio download link without downloading!"
    )

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a direct JioSaavn or YouTube URL\n"
        "2. Or send a search query (works mostly for YouTube)\n"
        "I will reply with the best audio stream direct URL you can open or download."
    )

if __name__ == "__main__":
    print("Bot started...")
    app.run()
