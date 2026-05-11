import os
import httpx
import discord

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
INGEST_URL = os.getenv("INGEST_URL", "http://api:8000/ingest")

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"synthetic-wall bot ready as {bot.user}")
    print(f"watching channel {CHANNEL_ID}")
    print(f"guilds: {[str(g) for g in bot.guilds]}")


@bot.event
async def on_message(message: discord.Message):
    print(f"MSG channel={message.channel.id} author={message.author} type={message.type} content={repr(message.content[:80])} snapshots={len(getattr(message,'message_snapshots',[]))}")

    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return

    text = message.content
    image_url = None

    if not text and hasattr(message, "message_snapshots") and message.message_snapshots:
        snap = message.message_snapshots[0]
        text = snap.content or ""
        if not text and snap.attachments:
            image_url = snap.attachments[0].url
            text = f"[Attachment: {snap.attachments[0].filename}]"

    if message.attachments:
        image_url = message.attachments[0].url
        if not text:
            text = f"[Attachment: {message.attachments[0].filename}]"

    if not text.strip():
        print("empty text, skipping")
        return

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            await client.post(
                INGEST_URL,
                json={"source": "discord", "raw_text": text, "image_url": image_url},
            )
        await message.add_reaction("✅")
    except Exception as e:
        import traceback; traceback.print_exc(); print(f"ingest failed: {type(e).__name__}: {e}")
        await message.add_reaction("❌")


bot.run(TOKEN)
