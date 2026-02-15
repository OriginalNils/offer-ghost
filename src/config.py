import os
import json
from pathlib import Path

# Base
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = json.loads(os.getenv("TELEGRAM_ALLOWED_USERS", "[]"))

# Marktguru
MARKTGURU_API_KEY = os.getenv("MARKTGURU_API_KEY")
MARKTGURU_CLIENT_KEY = os.getenv("MARKTGURU_CLIENT_KEY", "")
ZIP_CODE = os.getenv("ZIP_CODE", "65203")
STORES = os.getenv("STORES", "rewe,lidl,aldi-sued,kaufland").split(",")

# AI
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "google/gemini-2.5-flash-lite")

# Deal Settings
MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "6"))

# Files
DEALS_FILE = DATA_DIR / "deals.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"
HISTORY_FILE = DATA_DIR / "deal_history.json"

# Categories
CATEGORIES = {
    "🍎": "Obst & Gemüse",
    "🥩": "Fleisch & Fisch",
    "🥛": "Milchprodukte & Eier",
    "🥤": "Getränke",
    "🍫": "Süßes & Snacks",
    "🍞": "Brot & Backwaren",
    "🧊": "Tiefkühl",
    "🥫": "Konserven & Vorrat",
    "🧴": "Haushalt & Drogerie",
    "📦": "Sonstiges"
}

CATEGORY_EMOJIS = {v: k for k, v in CATEGORIES.items()}

print(f"✓ Config geladen: {len(STORES)} Stores, {len(TELEGRAM_ALLOWED_USERS)} User")
