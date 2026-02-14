import os
from dotenv import load_dotenv

load_dotenv()

# API Keys aus .env
MARKTGURU_API_KEY = os.getenv("MARKTGURU_API_KEY")
MARKTGURU_CLIENT_KEY = os.getenv("MARKTGURU_CLIENT_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Sucheinstellungen
ZIP_CODE = "65203"
SEARCH_LIMIT = 20
TRACKED_STORES = ["rewe", "lidl", "aldi-sued", "kaufland"]

AI_MODEL = "google/gemini-2.5-flash-lite"

# Pfade
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)