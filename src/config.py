import os
import yaml
import logging
from dotenv import load_dotenv

# Logging ZUERST konfigurieren, bevor andere Imports
logging.basicConfig(
    level=logging.INFO,  # ← Auf DEBUG gesetzt für maximale Info
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.debug("=== CONFIG: Modul-Initialisierung gestartet ===")

# .env laden
load_dotenv()
logger.debug("✓ .env geladen")

# API Keys aus .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MARKTGURU_API_KEY = os.getenv("MARKTGURU_API_KEY")
MARKTGURU_CLIENT_KEY = os.getenv("MARKTGURU_CLIENT_KEY")

logger.debug(f"API Keys Status:")
logger.debug(f"  OPENROUTER_API_KEY: {'✓ SET' if OPENROUTER_API_KEY else '✗ MISSING'}")
logger.debug(f"  MARKTGURU_API_KEY: {'✓ SET' if MARKTGURU_API_KEY else '✗ MISSING'}")
logger.debug(f"  MARKTGURU_CLIENT_KEY: {'✓ SET' if MARKTGURU_CLIENT_KEY else '✗ MISSING'}")

# Sucheinstellungen
ZIP_CODE = "65203"
SEARCH_LIMIT = 750

# AI-Einstellungen
AI_MODEL = "google/gemini-2.5-flash-lite"
AI_BATCH_SIZE = 50

logger.debug(f"Konfiguration:")
logger.debug(f"  ZIP_CODE: {ZIP_CODE}")
logger.debug(f"  SEARCH_LIMIT: {SEARCH_LIMIT}")
logger.debug(f"  AI_MODEL: {AI_MODEL}")
logger.debug(f"  AI_BATCH_SIZE: {AI_BATCH_SIZE}")

# Pfade
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, ".ai_cache")

logger.debug(f"Pfade:")
logger.debug(f"  BASE_DIR: {BASE_DIR}")
logger.debug(f"  DATA_DIR: {DATA_DIR}")
logger.debug(f"  CACHE_DIR: {CACHE_DIR}")

# Verzeichnisse erstellen
for directory in [DATA_DIR, CACHE_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.debug(f"✓ Verzeichnis erstellt: {directory}")
    else:
        logger.debug(f"✓ Verzeichnis existiert: {directory}")

# Stores aus YAML laden
stores_yaml_path = os.path.join(BASE_DIR, 'config', 'stores.yaml')
logger.debug(f"Lade Stores aus: {stores_yaml_path}")

try:
    with open(stores_yaml_path, 'r', encoding='utf-8') as f:
        STORES_CONFIG = yaml.safe_load(f)
        logger.debug(f"✓ YAML geladen: {STORES_CONFIG}")
        
        TRACKED_STORES = [
            slug for slug, data in STORES_CONFIG['stores'].items() 
            if data.get('enabled', False)
        ]
        logger.debug(f"✓ Aktive Stores: {TRACKED_STORES}")
except Exception as e:
    logger.error(f"✗ Fehler beim Laden von stores.yaml: {e}")
    raise

# ============= EMAIL CONFIG =============
EMAIL_ENABLED = True
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_USE_TLS = True

# Deine Gmail-Adresse (oder anderer Provider)
EMAIL_FROM = os.getenv("EMAIL_GOOGLE")
EMAIL_FROM_NAME = "Offer Ghost"

# App-Passwort (nicht dein normales Passwort!)
# Anleitung: https://support.google.com/accounts/answer/185833
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Empfänger (kann später auch über UI konfiguriert werden)
EMAIL_RECIPIENTS = [os.getenv("EMAIL_RECIPTANT")]

# Report-Zeitplan
EMAIL_REPORT_DAY = "Sunday"  # Wochentag für Report
EMAIL_REPORT_TIME = "18:00"  # Uhrzeit (24h Format)



# ============= TELEGRAM BOT =============
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USER")

# Benachrichtigungen
TELEGRAM_NOTIFY_NEW_DEALS = True
TELEGRAM_NOTIFY_FAVORITES = True


# Log-Datei hinzufügen (nach Verzeichnis-Erstellung)
log_file_handler = logging.FileHandler(
    os.path.join(DATA_DIR, 'scraper.log'), 
    encoding='utf-8'
)
log_file_handler.setLevel(logging.DEBUG)
log_file_handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
)
logging.getLogger().addHandler(log_file_handler)

logger.debug("✓ Log-Datei konfiguriert")
logger.debug("=== CONFIG: Modul vollständig geladen ===")
