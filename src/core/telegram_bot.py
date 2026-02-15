"""
Telegram Bot für Offer Ghost.
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from datetime import datetime
from src.config import *

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot für Offer Ghost."""
    
    def __init__(self, tracker, favorites_manager):
        self.enabled = TELEGRAM_ENABLED
        self.token = TELEGRAM_BOT_TOKEN
        self.allowed_users = TELEGRAM_ALLOWED_USERS
        self.tracker = tracker
        self.favorites = favorites_manager
        
        self.app = None
        
        if self.enabled and self.token:
            self.app = Application.builder().token(self.token).build()
            self._setup_handlers()
            logger.info(f"Telegram Bot initialisiert für {len(self.allowed_users)} Benutzer")
        else:
            logger.warning("Telegram Bot disabled or not configured")
    
    def _is_authorized(self, user_id: int) -> bool:
        """Prüft ob User autorisiert ist."""
        return user_id in self.allowed_users
    
    def _setup_handlers(self):
        """Registriert Command-Handlers."""
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("deals", self.cmd_deals))
        self.app.add_handler(CommandHandler("favorites", self.cmd_favorites))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("search", self.cmd_search))
        self.app.add_handler(CommandHandler("scan", self.cmd_scan))
        self.app.add_handler(CommandHandler("expiring", self.cmd_expiring))
        
        # Message handler für Text (für search ohne /command)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start Command."""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text(
                "⛔ Zugriff verweigert!\n\n"
                f"Deine User-ID: `{user_id}`\n"
                "Füge diese ID zu TELEGRAM_ALLOWED_USERS hinzu.",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(
            "👻 *Offer Ghost Bot*\n\n"
            "Willkommen! Ich helfe dir die besten Deals zu finden.\n\n"
            "*Verfügbare Commands:*\n"
            "🔥 /deals - Top Deals\n"
            "⭐ /favorites - Deine Favoriten\n"
            "🔍 /search <produkt> - Produkt suchen\n"
            "📊 /stats - Statistiken\n"
            "⏰ /expiring - Läuft bald ab\n"
            "🔄 /scan - Neuer Scan\n"
            "❓ /help - Hilfe\n\n"
            "Du kannst auch einfach einen Produktnamen schreiben!",
            parse_mode='Markdown'
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        await update.message.reply_text(
            "📚 *Offer Ghost Hilfe*\n\n"
            "*Commands:*\n\n"
            "🔥 `/deals` - Zeigt die Top 5 Deals\n"
            "⭐ `/favorites` - Deine Favoriten-Liste\n"
            "🔍 `/search Milch` - Sucht nach Produkten\n"
            "📊 `/stats` - Zeigt Statistiken\n"
            "⏰ `/expiring` - Angebote die bald ablaufen\n"
            "🔄 `/scan` - Startet neuen Scan\n\n"
            "*Beispiele:*\n"
            "`/search Nutella`\n"
            "`/deals`\n"
            "oder einfach: `Schokolade`",
            parse_mode='Markdown'
        )
    
    async def cmd_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Deals Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        await update.message.reply_text("🔍 Suche nach Deals...")
        
        # Top Deals finden
        deals = []
        for product_id, product in self.tracker.products.items():
            if product_id in self.tracker.price_history:
                for store, history in self.tracker.price_history[product_id].items():
                    if len(history) >= 2:
                        recent_prices = [h['unit_price'] for h in history[-7:]]
                        if len(recent_prices) >= 2:
                            avg_price = sum(recent_prices) / len(recent_prices)
                            current_price = recent_prices[-1]
                            
                            if current_price < avg_price * 0.85:
                                savings_percent = int(((avg_price - current_price) / avg_price) * 100)
                                brand = self.tracker.brands.get(product['brand_id'], {})
                                
                                deals.append({
                                    'name': product['name'],
                                    'brand': brand.get('name', ''),
                                    'store': store,
                                    'current_price': current_price,
                                    'avg_price': avg_price,
                                    'savings_percent': savings_percent,
                                    'base_unit': product['base_unit']
                                })
        
        if not deals:
            await update.message.reply_text(
                "😕 Keine Deals gefunden.\n\n"
                "Führe mehrere Scans über mehrere Tage durch um Preisverläufe zu tracken!",
                parse_mode='Markdown'
            )
            return
        
        # Sortiere nach Ersparnis
        deals.sort(key=lambda x: x['savings_percent'], reverse=True)
        top_deals = deals[:5]
        
        message = "🔥 *Top 5 Deals:*\n\n"
        
        for i, deal in enumerate(top_deals, 1):
            message += (
                f"{i}. *{deal['name']}*\n"
                f"   {deal['brand']} • {deal['store'].upper()}\n"
                f"   💰 *{deal['current_price']:.2f}€*/{deal['base_unit']}"
                f" (statt {deal['avg_price']:.2f}€)\n"
                f"   💵 Spare *{deal['savings_percent']}%*\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Favorites Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        detailed = self.favorites.get_favorites_with_details(self.tracker)
        
        if not detailed:
            await update.message.reply_text(
                "⭐ Du hast noch keine Favoriten!\n\n"
                "Füge Produkte über die Web-UI hinzu.",
                parse_mode='Markdown'
            )
            return
        
        message = f"⭐ *Deine Favoriten ({len(detailed)}):*\n\n"
        
        for fav in detailed[:10]:
            message += f"📦 *{fav['name']}*\n"
            
            if fav['best_price']:
                message += (
                    f"   💰 *{fav['best_price']:.2f}€*/{fav['base_unit']}"
                    f" bei {fav['best_store'].upper()}\n"
                )
                if len(fav['current_prices']) > 1:
                    message += f"   📍 Verfügbar in {len(fav['current_prices'])} Stores\n"
            else:
                message += "   ⚠️ Aktuell nicht verfügbar\n"
            
            message += "\n"
        
        if len(detailed) > 10:
            message += f"\n... und {len(detailed) - 10} weitere\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stats Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        total_products = len(self.tracker.products)
        total_brands = len(self.tracker.brands)
        total_favorites = len(self.favorites.get_all_favorites())
        
        # Zähle verfügbare Produkte heute
        today = datetime.now().strftime("%Y-%m-%d")
        available_today = 0
        
        for product_id in self.tracker.products:
            if product_id in self.tracker.price_history:
                for store, history in self.tracker.price_history[product_id].items():
                    if history and history[-1]['date'] == today:
                        available_today += 1
                        break
        
        message = (
            "📊 *Offer Ghost Statistiken*\n\n"
            f"📦 Produkte: *{total_products}*\n"
            f"🏷️ Marken: *{total_brands}*\n"
            f"⭐ Favoriten: *{total_favorites}*\n"
            f"✅ Heute verfügbar: *{available_today}*\n\n"
            f"🕐 Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ Bitte gib einen Suchbegriff an!\n\n"
                "Beispiel: `/search Milch`",
                parse_mode='Markdown'
            )
            return
        
        query = ' '.join(context.args).lower()
        await self._search_products(update, query)
    
    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Scan Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        await update.message.reply_text(
            "🔄 Scan wird gestartet...\n\n"
            "Dies kann 30-60 Sekunden dauern. "
            "Ich melde mich wenn fertig! ⏳"
        )
        
        # Note: Actual scan would be triggered via API call
        # For now, just inform user
        await update.message.reply_text(
            "ℹ️ Scan-Funktion muss über die Web-UI oder API ausgeführt werden.\n\n"
            "Alternativ: Öffne http://192.168.178.98:5000 und klicke 'Jetzt scannen'"
        )
    
    async def cmd_expiring(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Expiring Command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        today = datetime.now().strftime("%Y-%m-%d")
        expiring = []
        
        for product_id, product in self.tracker.products.items():
            if product_id in self.tracker.price_history:
                for store, history in self.tracker.price_history[product_id].items():
                    if history and history[-1]['date'] == today:
                        latest = history[-1]
                        valid_until = latest.get('valid_until', '')
                        
                        if valid_until:
                            try:
                                valid_date = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                                days = (valid_date.date() - datetime.now().date()).days
                                
                                if 0 <= days <= 3:
                                    brand = self.tracker.brands.get(product['brand_id'], {})
                                    expiring.append({
                                        'name': product['name'],
                                        'brand': brand.get('name', ''),
                                        'store': store,
                                        'price': latest['unit_price'],
                                        'base_unit': product['base_unit'],
                                        'days': days
                                    })
                            except:
                                pass
        
        if not expiring:
            await update.message.reply_text("✅ Keine Angebote laufen in den nächsten 3 Tagen ab!")
            return
        
        expiring.sort(key=lambda x: x['days'])
        
        message = f"⏰ *Läuft bald ab ({len(expiring)}):*\n\n"
        
        for item in expiring[:10]:
            days_text = "HEUTE" if item['days'] == 0 else f"in {item['days']} Tag{'en' if item['days'] > 1 else ''}"
            message += (
                f"{'🔴' if item['days'] == 0 else '🟡'} *{item['name']}*\n"
                f"   {item['store'].upper()} • {item['price']:.2f}€/{item['base_unit']}\n"
                f"   Läuft ab: *{days_text}*\n\n"
            )
        
        if len(expiring) > 10:
            message += f"... und {len(expiring) - 10} weitere"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle normale Text-Nachrichten als Search."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        query = update.message.text.lower()
        await self._search_products(update, query)
    
    async def _search_products(self, update: Update, query: str):
        """Sucht nach Produkten."""
        results = []
        
        for product_id, product in self.tracker.products.items():
            if query in product['name'].lower():
                brand = self.tracker.brands.get(product['brand_id'], {})
                results.append({
                    'name': product['name'],
                    'brand': brand.get('name', ''),
                    'category': product['category'],
                    'stores': product['stores_available']
                })
        
        if not results:
            await update.message.reply_text(
                f"😕 Keine Produkte gefunden für:\n*{query}*",
                parse_mode='Markdown'
            )
            return
        
        message = f"🔍 *Gefunden ({len(results)}):*\n\n"
        
        for item in results[:8]:
            message += (
                f"📦 *{item['name']}*\n"
                f"   {item['brand']} • {item['category']}\n"
                f"   🏪 {', '.join([s.upper() for s in item['stores']])}\n\n"
            )
        
        if len(results) > 8:
            message += f"\n... und {len(results) - 8} weitere Ergebnisse"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def send_notification(self, user_id: int, message: str):
        """Sendet Benachrichtigung an User."""
        if not self.enabled or not self.app:
            return
        
        try:
            await self.app.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    async def run(self):
        """Startet den Bot."""
        if not self.enabled or not self.app:
            logger.warning("Telegram bot not started (disabled or not configured)")
            return
        
        try:
            logger.info("Starting Telegram Bot...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
    
    async def stop(self):
        """Stoppt den Bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
