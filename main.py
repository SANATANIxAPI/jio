from pyrogram import Client, filters
from pyrogram.types import Message
import aiohttp

# Telegram Bot credentials
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "7512249863:AAF5XnrPikoQSr4546P0_6pf7wZR822MICg"

# Initialize the Pyrogram Client
app = Client("jiosaavn_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

SAAVN_SEARCH_API = "https://saavn.dev/api/search/songs"
SAAVN_SONG_API = "https://saavn.dev/api/songs/{}"

# Filter to exclude commands
def is_not_command(_, __, message):
    return not (message.text and message.text.startswith("/"))

non_command_filter = filters.create(is_not_command)

async def search_song_and_get_stream(query: str):
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Search song
            async with session.get(SAAVN_SEARCH_API, params={"query": query, "limit": 1}) as res:
                result = await res.json()
                results = result.get("data", {}).get("results", [])
                if not results:
                    return None

                song = results[0]
                song_id = song.get("id")

            # 2. Get full song info using song ID
            async with session.get(SAAVN_SONG_API.format(song_id)) as res:
                song_data = await res.json()
                song_info = song_data.get("data", [])[0]
                song_name = song_info.get("name", "Unknown")
                artist = song_info.get("primaryArtists", "Unknown")
                media_url = song_info.get("downloadUrl", [{}])[-1].get("link")  # 320kbps link
                return {
                    "title": song_name,
                    "artist": artist,
                    "media_url": media_url
                }
        except Exception as e:
            print(f"Error fetching stream: {e}")
            return None

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text("Hi! Send me a JioSaavn song name or URL, and I’ll give you the stream/download link.")

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    await message.reply_text("Send any JioSaavn song name or URL to get the audio stream/download link.")

@app.on_message(filters.text & non_command_filter)
async def handle_message(client, message: Message):
    query = message.text.strip()
    msg = await message.reply_text("🔍 Searching...")

    data = await search_song_and_get_stream(query)
    if not data:
        await msg.edit_text("❌ Song not found.")
        return

    reply = (
        f"🎵 *{data['title']}*\n"
        f"👤 {data['artist']}\n"
        f"🔗 [Stream/Download]({data['media_url']})"
    )
    await msg.edit_text(reply, parse_mode="markdown", disable_web_page_preview=True)

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
