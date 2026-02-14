"""
Konfigurations-Template für Offer Ghost.
Kopiere diese Datei zu config.py und fülle deine Werte ein.
"""

import os

# ===== API KEYS =====
OPENROUTER_API_KEY = "your-api-key-here"  # Ersetze mit deinem Key

# ===== SCRAPING CONFIG =====
ZIP_CODE = "65203"  # Deine PLZ
TRACKED_STORES = ["rewe", "lidl", "aldi-sued", "kaufland"]

# ===== DATA STORAGE =====
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, ".ai_cache")  # ← NEU

# ===== AI CONFIG =====
AI_MODEL = "google/gemini-2.5-flash-lite"
AI_BATCH_SIZE = 75
AI_USE_CACHE = True

# ===== STORES CONFIG =====
STORES_CONFIG = {
    "api_base": "https://api.aktionsfinder.at/v1",
    "stores": {
        "rewe": {"name": "REWE", "id": "rewe"},
        "lidl": {"name": "Lidl", "id": "lidl"},
        "aldi-sued": {"name": "Aldi Süd", "id": "aldi-sued"},
        "kaufland": {"name": "Kaufland", "id": "kaufland"}
    }
}

# ===== LOGGING =====
LOGGING_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
