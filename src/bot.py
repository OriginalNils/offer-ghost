#!/usr/bin/env python3
"""
Offer Ghost 2.0 - Deal-Only Telegram Bot
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime
from typing import List, Dict

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from src.config import *
from src.scrapers.marktguru import MarktguruScraper
from src.core.deal_manager import DealManager
from src.core.favorites import FavoritesManager
from src.core.notifications import NotificationManager

# Logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class OfferGhostBot:
    """Hauptbot-Klasse"""
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.deal_manager = DealManager(DEALS_FILE, HISTORY_FILE, MIN_DISCOUNT_PERCENT)
        self.favorites = FavoritesManager(FAVORITES_FILE)
        self.notifications = NotificationManager(self.bot)
        
        logger.info("🤖 Offer Ghost Bot initialisiert")
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check ob User autorisiert"""
        return user_id in TELEGRAM_ALLOWED_USERS
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start Command"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ Nicht autorisiert!")
            return
        
        text = """
👻 <b>Offer Ghost Bot 2.0</b>

Ich finde die besten Deals für dich!

<b>🔥 Commands:</b>
/deals - Alle aktuellen Deals
/top - Top 10 nach Rabatt
/favorites - Deine Favoriten
/notify - Push-Benachrichtigungen
/stats - Statistiken
/help - Hilfe

<b>🎯 Suche:</b>
Schreib einfach ein Produkt (z.B. "Nutella")

<b>📂 Kategorien:</b>
/deals süßes
/deals getränke
/deals obst
        """
        await update.message.reply_text(text.strip(), parse_mode="HTML")
    
    async def cmd_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Zeige alle Deals"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        # Check für Kategorie-Filter
        category_filter = None
        if context.args:
            category_filter = " ".join(context.args)
        
        deals = self.deal_manager.get_deals(category=category_filter)
        
        if not deals:
            msg = "😔 Keine Deals gefunden"
            if category_filter:
                msg += f" für '{category_filter}'"
            await update.message.reply_text(msg)
            return
        
        # Gruppiere nach Store
        deals_by_store = {}
        for deal in deals:
            store = deal["store"]
            if store not in deals_by_store:
                deals_by_store[store] = []
            deals_by_store[store].append(deal)
        
        # Sende Deals (max 20 pro Message)
        count = 0
        for store, store_deals in deals_by_store.items():
            msg = f"🏪 <b>{store}</b>\n\n"
            
            for deal in store_deals[:20]:
                msg += self._format_deal(deal) + "\n\n"
                count += 1
                
                if count >= 20:
                    break
            
            await update.message.reply_text(msg.strip(), parse_mode="HTML")
            
            if count >= 20:
                await update.message.reply_text(
                    f"... und {len(deals) - 20} weitere Deals!\n"
                    f"Nutze /top für die besten."
                )
                break
    
    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Top 10 Deals"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        top_deals = self.deal_manager.get_top_deals(limit=10)
        
        if not top_deals:
            await update.message.reply_text("😔 Keine Deals verfügbar")
            return
        
        msg = "🔥 <b>Top 10 Deals nach Rabatt</b>\n\n"
        
        for i, deal in enumerate(top_deals, 1):
            msg += f"{i}. {self._format_deal(deal)}\n\n"
        
        await update.message.reply_text(msg.strip(), parse_mode="HTML")
    
    def _format_deal(self, deal: Dict) -> str:
        """Formatiere Deal für Anzeige"""
        emoji = CATEGORY_EMOJIS.get(deal.get("category", ""), "📦")
        
        text = f"{emoji} <b>{deal['name']}</b>"
        
        if deal.get("amount"):
            text += f" {deal['amount']}"
        
        text += f"\n💰 {deal['price']:.2f}€"
        
        if deal.get("base_price"):
            text += f" <s>{deal['base_price']:.2f}€</s>"
            text += f" <b>-{deal['discount_percent']}%</b>"
            text += f" (spare {deal['saved_amount']:.2f}€)"
        
        text += f"\n🏪 {deal['store']}"
        
        if deal.get("days_left") is not None and deal["days_left"] >= 0:
            if deal["days_left"] == 0:
                text += " • ⏰ <b>Heute letzter Tag!</b>"
            elif deal["days_left"] <= 2:
                text += f" • ⏰ Noch {deal['days_left']} Tage"
        
        return text

    async def cmd_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verwalte Favoriten"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        # Kein Argument: Liste anzeigen
        if not context.args:
            favs = self.favorites.get(user_id)
            
            if not favs:
                text = "⭐ <b>Deine Favoriten</b>\n\n"
                text += "Du hast noch keine Favoriten.\n\n"
                text += "<b>Hinzufügen:</b>\n"
                text += "/favorites add Nutella\n"
                text += "/favorites add Milch\n\n"
                text += "<b>Entfernen:</b>\n"
                text += "/favorites remove Nutella"
            else:
                text = "⭐ <b>Deine Favoriten:</b>\n\n"
                for fav in favs:
                    text += f"• {fav}\n"
                text += f"\n<b>Gesamt:</b> {len(favs)} Favoriten\n\n"
                text += "Hinzufügen: /favorites add Produkt\n"
                text += "Entfernen: /favorites remove Produkt"
            
            await update.message.reply_text(text, parse_mode="HTML")
            return
        
        # Mit Argument: add/remove
        action = context.args[0].lower()
        
        if action == "add" and len(context.args) > 1:
            keyword = " ".join(context.args[1:])
            success = self.favorites.add(user_id, keyword)
            
            if success:
                await update.message.reply_text(
                    f"✅ '{keyword}' zu Favoriten hinzugefügt!\n\n"
                    f"Du bekommst Benachrichtigungen wenn neue Deals verfügbar sind."
                )
            else:
                await update.message.reply_text(f"ℹ️ '{keyword}' ist bereits in deinen Favoriten")
        
        elif action == "remove" and len(context.args) > 1:
            keyword = " ".join(context.args[1:])
            success = self.favorites.remove(user_id, keyword)
            
            if success:
                await update.message.reply_text(f"✅ '{keyword}' aus Favoriten entfernt")
            else:
                await update.message.reply_text(f"❌ '{keyword}' nicht in deinen Favoriten gefunden")
        
        elif action == "clear":
            self.favorites.clear(user_id)
            await update.message.reply_text("✅ Alle Favoriten gelöscht")
        
        else:
            await update.message.reply_text(
                "❌ Ungültiger Befehl\n\n"
                "Nutze:\n"
                "/favorites add <Produkt>\n"
                "/favorites remove <Produkt>\n"
                "/favorites clear"
            )
    
    async def cmd_notify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Push-Benachrichtigungen ein/aus"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        if not context.args:
            status = "🔔 AN" if self.notifications.is_enabled(user_id) else "🔕 AUS"
            text = f"<b>Push-Benachrichtigungen:</b> {status}\n\n"
            text += "<b>Ändern:</b>\n"
            text += "/notify on - Aktivieren\n"
            text += "/notify off - Deaktivieren\n\n"
            text += "<b>Du bekommst Benachrichtigungen bei:</b>\n"
            text += "• Neuen Deals zu deinen Favoriten\n"
            text += f"• Neuen Top-Deals (>{MIN_DISCOUNT_PERCENT}% Rabatt)"
            
            await update.message.reply_text(text, parse_mode="HTML")
            return
        
        action = context.args[0].lower()
        
        if action == "on":
            self.notifications.enable(user_id)
            await update.message.reply_text(
                "🔔 <b>Push-Benachrichtigungen aktiviert!</b>\n\n"
                "Du bekommst jetzt Benachrichtigungen bei neuen Deals.",
                parse_mode="HTML"
            )
        elif action == "off":
            self.notifications.disable(user_id)
            await update.message.reply_text(
                "🔕 Push-Benachrichtigungen deaktiviert",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("Nutze: /notify on oder /notify off")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Zeige Statistiken"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        stats = self.deal_manager.get_stats()
        favs = self.favorites.get(user_id)
        
        text = "📊 <b>Statistiken</b>\n\n"
        text += f"🔥 <b>Deals:</b> {stats['total_deals']}\n"
        text += f"🏪 <b>Märkte:</b> {', '.join(stats['stores'])}\n"
        text += f"💯 <b>Ø Rabatt:</b> {stats['avg_discount']}%\n"
        text += f"🎯 <b>Max Rabatt:</b> {stats['max_discount']}%\n"
        text += f"⭐ <b>Favoriten:</b> {len(favs)}\n\n"
        
        text += "<b>📂 Kategorien:</b>\n"
        for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1])[:5]:
            emoji = CATEGORY_EMOJIS.get(cat, "📦")
            text += f"{emoji} {cat}: {count}\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hilfe"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        text = """
<b>📚 Hilfe - Offer Ghost Bot</b>

<b>🔥 Deal Commands:</b>
/deals - Alle aktuellen Deals
/deals süßes - Nur Süßigkeiten
/top - Top 10 nach Rabatt

<b>🔍 Suche:</b>
Schreib einfach ein Produkt:
"Nutella" oder "Cola"

<b>⭐ Favoriten:</b>
/favorites - Liste anzeigen
/favorites add Nutella
/favorites remove Nutella

<b>🔔 Benachrichtigungen:</b>
/notify on - Aktivieren
/notify off - Deaktivieren

<b>📊 Info:</b>
/stats - Statistiken
/help - Diese Hilfe

<b>📂 Verfügbare Kategorien:</b>
Obst & Gemüse, Fleisch & Fisch,
Milchprodukte & Eier, Getränke,
Süßes & Snacks, Brot & Backwaren,
Tiefkühl, Konserven & Vorrat,
Haushalt & Drogerie
        """
        await update.message.reply_text(text.strip(), parse_mode="HTML")
    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle freie Suche (ohne /)"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        query = update.message.text.strip().lower()
        
        if len(query) < 2:
            return
        
        # Suche in Deals
        all_deals = self.deal_manager.get_deals()
        
        results = []
        for deal in all_deals:
            name_lower = deal.get("name", "").lower()
            desc_lower = deal.get("description", "").lower()
            
            if query in name_lower or query in desc_lower:
                results.append(deal)
        
        if not results:
            await update.message.reply_text(
                f"😔 Keine Deals gefunden für '{query}'\n\n"
                f"💡 Tipp: Füge '{query}' zu deinen Favoriten hinzu:\n"
                f"/favorites add {query}"
            )
            return
        
        # Sortiere nach Rabatt
        results.sort(key=lambda x: x.get("discount_percent", 0), reverse=True)
        
        msg = f"🔍 <b>Suchergebnisse für '{query}'</b>\n"
        msg += f"Gefunden: {len(results)} Deals\n\n"
        
        for deal in results[:10]:  # Max 10
            msg += self._format_deal(deal) + "\n\n"
        
        if len(results) > 10:
            msg += f"... und {len(results) - 10} weitere"
        
        await update.message.reply_text(msg.strip(), parse_mode="HTML")
    
    async def scan_deals(self):
        """Scanne alle Stores nach Deals"""
        logger.info("🔍 Starte Deal-Scan...")
        
        all_deals = []
        
        for store in STORES:
            try:
                scraper = MarktguruScraper(store, ZIP_CODE, MARKTGURU_API_KEY)
                deals = scraper.fetch_deals()
                all_deals.extend(deals)
                
                # Kurze Pause zwischen Stores
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Fehler bei {store}: {e}")
        
        # Update Deal-Manager
        result = self.deal_manager.update_deals(all_deals)
        
        logger.info(
            f"✅ Scan abgeschlossen: {result['total']} Deals, "
            f"{result['new']} neu"
        )
        
        # Benachrichtigungen senden
        if result['new'] > 0:
            await self._send_notifications(result['new_deals'])
        
        return result
    
    async def _send_notifications(self, new_deals: List[Dict]):
        """Sende Notifications an alle User"""
        for user_id in TELEGRAM_ALLOWED_USERS:
            try:
                # Finde Favoriten-Matches
                fav_matches = self.favorites.match_deals(user_id, new_deals)
                
                # Sende Notification
                await self.notifications.notify_new_deals(
                    user_id, 
                    new_deals, 
                    fav_matches
                )
                
            except Exception as e:
                logger.error(f"Notification-Fehler für User {user_id}: {e}")
    
    def run(self):
        """Starte Bot"""
        logger.info("🚀 Starte Offer Ghost Bot...")
        
        # Initialer Scan
        asyncio.run(self.scan_deals())
        
        # Telegram Application
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Command Handlers
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("deals", self.cmd_deals))
        app.add_handler(CommandHandler("top", self.cmd_top))
        app.add_handler(CommandHandler("favorites", self.cmd_favorites))
        app.add_handler(CommandHandler("notify", self.cmd_notify))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Text-Handler für Suche
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_search
        ))
        
        # Scheduler in separatem Thread
        import threading
        scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Starte Bot
        logger.info("✅ Bot läuft!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def _run_scheduler(self):
        """Scheduler für automatische Scans"""
        # Schedule alle X Stunden
        schedule.every(SCAN_INTERVAL_HOURS).hours.do(
            lambda: asyncio.run(self.scan_deals())
        )
        
        logger.info(f"⏰ Scheduler aktiv: Scan alle {SCAN_INTERVAL_HOURS}h")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check alle 60 Sekunden

# Health-Check HTTP-Server
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Keine Logs

def start_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("🏥 Health-Check Server läuft auf Port 8080")

# Main
if __name__ == "__main__":
    # Health-Check Server starten
    start_health_server()
    
    # Bot starten
    bot = OfferGhostBot()
    bot.run()

