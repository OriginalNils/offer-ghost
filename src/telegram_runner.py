"""
Telegram Bot Runner - Läuft parallel zum Flask Server.
"""

import asyncio
import logging
from src.core.product_tracker import ProductTracker
from src.core.favorites import FavoritesManager
from src.core.telegram_bot import TelegramBot
from src.config import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Hauptfunktion."""
    logger.info("Initialisiere Telegram Bot...")
    
    # Lade Tracker & Favorites
    tracker = ProductTracker(DATA_DIR)
    favorites = FavoritesManager(DATA_DIR)
    
    # Starte Bot
    bot = TelegramBot(tracker, favorites)
    
    if bot.enabled:
        await bot.run()
    else:
        logger.warning("Telegram Bot ist deaktiviert")


if __name__ == '__main__':
    asyncio.run(main())
