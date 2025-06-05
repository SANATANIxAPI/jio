from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import asyncio
import uuid

API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

app = Client("jiosaavn_only_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

SAAVN_API = "https://saavn.dev/api/search/songs"
url_map = {}

async def search_songs(query):
    params = {'query': query, 'limit': 5}
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SAAVN_API, params=params, headers=headers) as resp:
                data = await resp.json()
                if data.get('success') and data.get('data', {}).get('results'):
                    return data['data']['results']
                return None
        except Exception:
            return None

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Hi! Send me a JioSaavn URL or a song name.\n"
        "I will provide you song info and link.\n"
        "Note: Only JioSaavn is supported."
    )

@app.on_message(filters.text)
async def handle_message(client, message):
    if message.text.startswith("/"):
        return  # Ignore commands here

    text = message.text.strip()

    if "youtube.com" in text.lower() or "youtu.be" in text.lower():
        await message.reply_text("Sorry, I only support JioSaavn links and song names.")
        return

    if "jiosaavn.com" in text.lower():
        await message.reply_text(f"JioSaavn URL received:\n{text}\nYou can open this URL to listen/download.")
        return

    results = await search_songs(text)
    if not results:
        await message.reply_text("No songs found on JioSaavn for your query.")
        return

    keyboard = []
    for song in results:
        short_id = str(uuid.uuid4())[:8]
        url_map[short_id] = song['url']
        keyboard.append([InlineKeyboardButton(f"{song['name']} - {song.get('primaryArtists', 'Unknown')}", callback_data=f"dl:{short_id}")])

    await message.reply_text("Select a song:", reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(r"^dl:"))
async def callback_handler(client, cq):
    short_id = cq.data.split("dl:")[1]
    url = url_map.get(short_id)
    if not url:
        await cq.answer("Song URL not found!", show_alert=True)
        return

    await cq.answer()
    await cq.message.edit(f"Here is your JioSaavn song link:\n{url}")
    url_map.pop(short_id, None)

if __name__ == "__main__":
    print("JioSaavn only bot started...")
    app.run()
