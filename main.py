from pyrogram import Client, filters
from pyrogram.types import Message
import aiohttp
import asyncio

# Telegram Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Initialize the Pyrogram Client
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Saavn.dev API endpoint
SAAVN_API = "https://saavn.dev/api/search/songs"

async def search_songs(query):
    """Search songs using saavn.dev API"""
    params = {
        'query': query,
        'limit': 1  # Only top result
    }
    headers = {
        'User-Agent': 'Mozilla/5.0'
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

# Filter to exclude commands (messages starting with '/')
def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

@app.on_message(filters.text & non_command_filter)
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    
    if "jiosaavn.com" in text:
        # If direct JioSaavn URL, just reply with it
        await message.reply_text(f"Here is your JioSaavn link:\n{text}")
        return
    
    # Otherwise, treat as search query
    results = await search_songs(text)
    if not results:
        await message.reply_text("No results found for your query!")
        return
    
    first_song = results[0]
    song_name = first_song.get('name', 'Unknown')
    artist = first_song.get('primaryArtists', 'Unknown Artist')
    url = first_song.get('url', 'No URL available')
    
    reply_text = (
        f"🎵 *{song_name}*\n"
        f"👤 {artist}\n"
        f"🔗 [Listen here]({url})"
    )
    
    # Use markdown style to format message
    await message.reply_text(reply_text, parse_mode="markdown")

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hi! Send me a JioSaavn URL or a song name, and I'll send you the direct link."
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "Usage:\n"
        "1. Send a JioSaavn URL directly\n"
        "2. Or send a song name to search\n\n"
        "Example URL:\nhttps://www.jiosaavn.com/song/let-me-love-you/KD8zfRtiYms\n"
        "Example search:\nLet Me Love You"
    )

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
