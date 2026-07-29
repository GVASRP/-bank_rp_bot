import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не указан в .env файле")

BOT_PROXY = os.getenv("BOT_PROXY")
KALTENGRAM_WEB_URL = os.getenv("KALTENGRAM_WEB_URL", "https://kalten-gram.vercel.app")
