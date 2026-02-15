import os
import json
import logging
from pathlib import Path

# Base
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Debug
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = json.loads(os.getenv("TELEGRAM_ALLOWED_USERS", "[]"))

# Marktguru
MARKTGURU_API_KEY = os.getenv("MARKTGURU_API_KEY")
MARKTGURU_CLIENT_KEY = os.getenv("MARKTGURU_CLIENT_KEY", "")
ZIP_CODE = os.getenv("ZIP_CODE", "68161")
STORES = os.getenv("STORES", "rewe,lidl").split(",")

# Deal Settings
MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
SHOW_ALL_OFFERS = os.getenv("SHOW_ALL_OFFERS", "false").lower() == "true"
SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "6"))

# Files
DEALS_FILE = DATA_DIR / "deals.json"
FAVORITES_FILE = DATA_DIR / "favorites.json"
HISTORY_FILE = DATA_DIR / "deal_history.json"
DEBUG_DIR = DATA_DIR / "debug"
if DEBUG_MODE:
    DEBUG_DIR.mkdir(exist_ok=True)

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
if DEBUG_MODE:
    print(f"🔍 DEBUG MODE AKTIV - Log Level: {LOG_LEVEL}")
