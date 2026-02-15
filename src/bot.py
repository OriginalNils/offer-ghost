#!/usr/bin/env python3
"""Offer Ghost 2.0 - Deal-Only Telegram Bot"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import List, Dict
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from config import *
from scrapers.marktguru import MarktguruScraper
from core.deal_manager import DealManager
from core.favorites import FavoritesManager
from core.notifications import NotificationManager
from core.price_tracker import PriceTracker

# Logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class OfferGhostBot:
    """Hauptbot-Klasse"""
    
    def __init__(self):
        self.bot = None
        self.deal_manager = DealManager(DEALS_FILE, HISTORY_FILE, MIN_DISCOUNT_PERCENT, SHOW_ALL_OFFERS)
        self.favorites = FavoritesManager(FAVORITES_FILE)
        self.price_tracker = PriceTracker(PRICE_HISTORY_FILE)  # ← NEU
        self.notifications = None
        self.scan_task = None
        
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
/scan - Manueller Scan
/help - Hilfe

<b>🎯 Suche:</b>
Schreib einfach ein Produkt (z.B. "Nutella")
        """
        await update.message.reply_text(text.strip(), parse_mode="HTML")
    
    async def cmd_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Zeige Deals mit Filter-Option"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        # Check für Filter: /deals rabatte oder /deals alle
        show_type = "all"  # default
        category_filter = None
        
        if context.args:
            first_arg = context.args[0].lower()
            
            if first_arg in ["rabatte", "discount", "deals"]:
                show_type = "discount"
            elif first_arg in ["angebote", "alle", "all"]:
                show_type = "all"
            else:
                category_filter = " ".join(context.args)
        
        # Deals holen
        deals = self.deal_manager.get_deals(category=category_filter)
        
        # Filter nach Typ
        if show_type == "discount":
            deals = [d for d in deals if d.get("offer_type") == "discount"]
        
        if not deals:
            msg = "😔 Keine Deals gefunden"
            await update.message.reply_text(msg)
            return
        
        # Gruppiere nach Store
        deals_by_store = {}
        for deal in deals:
            store = deal["store"]
            if store not in deals_by_store:
                deals_by_store[store] = []
            deals_by_store[store].append(deal)
        
        # Sende Deals
        count = 0
        for store, store_deals in deals_by_store.items():
            msg = f"🏪 <b>{store}</b>\n\n"
            
            for deal in store_deals[:10]:
                msg += self._format_deal(deal) + "\n\n"
                count += 1
                
                if count >= 20:
                    break
            
            try:
                await update.message.reply_text(msg.strip(), parse_mode="HTML")
            except:
                pass
            
            if count >= 20:
                await update.message.reply_text(
                    f"... und {len(deals) - 20} weitere Deals!\nNutze /top für die besten."
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
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Zeige Statistiken"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        stats = self.deal_manager.get_stats()
        favs = self.favorites.get(user_id)
        price_stats = self.price_tracker.get_stats()
        
        text = "📊 <b>Statistiken</b>\n\n"
        text += f"🔥 <b>Deals:</b> {stats['total_deals']}\n"
        text += f"🏪 <b>Märkte:</b> {', '.join(stats['stores']) if stats['stores'] else 'Keine'}\n"
        text += f"💯 <b>Ø Rabatt:</b> {stats['avg_discount']}%\n"
        text += f"🎯 <b>Max Rabatt:</b> {stats['max_discount']}%\n"
        text += f"⭐ <b>Favoriten:</b> {len(favs)}\n"
        text += f"\n📊 <b>Price-Tracking:</b>\n"
        text += f"  Produkte: {price_stats['total_products']}\n"
        text += f"  Datenpunkte: {price_stats['total_price_points']}\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    
    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manueller Scan"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        await update.message.reply_text("🔍 Starte Scan...")
        
        result = await self.scan_deals()
        
        msg = f"✅ Scan abgeschlossen!\n\n"
        msg += f"📊 {result['total']} Deals gefunden\n"
        msg += f"🆕 {result['new']} neue Deals"
        
        await update.message.reply_text(msg)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hilfe"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        text = """
<b>📚 Hilfe</b>

<b>Commands:</b>
/deals - Alle Deals
/top - Top 10
/stats - Statistiken
/scan - Manueller Scan
/help - Diese Hilfe

<b>Suche:</b>
Schreib einfach: "Nutella"
        """
        await update.message.reply_text(text.strip(), parse_mode="HTML")
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Zeige Preis-Historie eines Produkts"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        if not context.args:
            await update.message.reply_text(
                "Nutze: /history <Produktname>\n\n"
                "Beispiel: /history Nutella"
            )
            return
        
        query = " ".join(context.args).lower()
        
        # Suche Produkt in aktuellen Deals
        deals = self.deal_manager.get_deals()
        
        found = None
        for deal in deals:
            if query in deal.get("name", "").lower():
                found = deal
                break
        
        if not found:
            await update.message.reply_text(f"❌ Produkt '{query}' nicht gefunden")
            return
        
        # Preis-Historie
        price_hist = found.get("price_history", {})
        
        text = f"📊 <b>{found['name']}</b>\n\n"
        
        text += f"💰 <b>Aktuell:</b> {found['price']:.2f}€\n"
        text += f"📉 <b>Niedrigster:</b> {price_hist.get('lowest_price', 0):.2f}€\n"
        text += f"📈 <b>Höchster:</b> {price_hist.get('highest_price', 0):.2f}€\n"
        text += f"📊 <b>Durchschnitt:</b> {price_hist.get('avg_price', 0):.2f}€\n\n"
        
        vs_avg = price_hist.get("vs_avg", 0)
        if vs_avg < 0:
            text += f"✅ {abs(vs_avg):.1f}% günstiger als Durchschnitt\n"
        elif vs_avg > 0:
            text += f"⚠️ {vs_avg:.1f}% teurer als Durchschnitt\n"
        
        offer_count = price_hist.get("offer_count", 0)
        text += f"\n🔥 Bereits {offer_count}x im Angebot gesehen\n"
        
        last_offer_days = price_hist.get("last_offer_days_ago")
        if last_offer_days:
            text += f"📅 Letztes Angebot: vor {last_offer_days} Tagen"
        
        await update.message.reply_text(text, parse_mode="HTML")

    
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle freie Suche"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return
        
        query = update.message.text.strip().lower()
        
        if len(query) < 2:
            return
        
        all_deals = self.deal_manager.get_deals()
        
        results = []
        for deal in all_deals:
            name_lower = deal.get("name", "").lower()
            desc_lower = deal.get("description", "").lower()
            
            if query in name_lower or query in desc_lower:
                results.append(deal)
        
        if not results:
            await update.message.reply_text(f"😔 Keine Deals gefunden für '{query}'")
            return
        
        results.sort(key=lambda x: x.get("discount_percent", 0), reverse=True)
        
        msg = f"🔍 <b>'{query}'</b> - {len(results)} Deals\n\n"
        
        for deal in results[:10]:
            msg += self._format_deal(deal) + "\n\n"
        
        if len(results) > 10:
            msg += f"... und {len(results) - 10} weitere"
        
        await update.message.reply_text(msg.strip(), parse_mode="HTML")
    
    def _format_deal(self, deal: Dict) -> str:
        """Formatiere Deal mit Preis-Historie"""
        emoji = CATEGORY_EMOJIS.get(deal.get("category", ""), "📦")
        offer_type = deal.get("offer_type", "offer")
        
        # Name + Brand
        text = f"{emoji} <b>{deal['name']}</b>"
        
        if deal.get("brand"):
            text += f" <i>({deal['brand']})</i>"
        
        # Menge
        if deal.get("amount"):
            text += f"\n📏 {deal['amount']}"
        
        # Preis
        text += f"\n💰 {deal['price']:.2f}€"
        
        # Rabatt-Info
        if offer_type == "discount" and deal.get("base_price"):
            text += f" <s>{deal['base_price']:.2f}€</s>"
            text += f" • <b>-{deal['discount_percent']}%</b>"
        elif offer_type == "offer":
            text += " • 🔥 <b>Angebot</b>"
        
        # NEU: Preis-Historie Badges
        price_hist = deal.get("price_history", {})
        
        if price_hist:
            badges = []
            
            # Tiefstpreis!
            if price_hist.get("is_lowest"):
                badges.append("🎯 <b>TIEFSTPREIS!</b>")
            
            # Unter Durchschnitt
            vs_avg = price_hist.get("vs_avg", 0)
            if vs_avg < -10:
                badges.append(f"📉 {abs(vs_avg):.0f}% unter Ø")
            
            # Trend
            trend = price_hist.get("trend")
            if trend == "falling":
                badges.append("⬇️ fallend")
            elif trend == "rising":
                badges.append("⬆️ steigend")
            
            if badges:
                text += f"\n{'  •  '.join(badges)}"
            
            # Letztes Angebot
            last_offer_days = price_hist.get("last_offer_days_ago")
            if last_offer_days and last_offer_days > 7:
                text += f"\n📅 Letztes Angebot: vor {last_offer_days}d"
        
        text += f"\n🏪 {deal['store']}"
        
        # Gültigkeit
        if deal.get("days_left") is not None:
            if deal["days_left"] == 0:
                text += " • ⏰ <b>Heute!</b>"
            elif deal["days_left"] <= 3:
                text += f" • ⏰ {deal['days_left']}d"
        
        return text


    
    async def scan_deals(self):
        """Scanne alle Stores"""
        logger.info("🔍 Starte Deal-Scan...")
        
        all_deals = []
        
        for store in STORES:
            try:
                scraper = MarktguruScraper(
                    store, 
                    ZIP_CODE, 
                    MARKTGURU_API_KEY, 
                    MARKTGURU_CLIENT_KEY,
                    debug_mode=DEBUG_MODE
                )
                deals = scraper.fetch_deals()
                
                if deals:
                    all_deals.extend(deals)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Fehler bei {store}: {e}")
        
        # NEU: Update Price-Tracking ZUERST
        price_stats = self.price_tracker.update_prices(all_deals)
        
        # NEU: Reichere Deals mit Preis-Historie an
        enriched_deals = []
        for deal in all_deals:
            enriched = self.price_tracker.enrich_deal(deal)
            enriched_deals.append(enriched)
        
        # Update Deal-Manager mit enriched deals
        result = self.deal_manager.update_deals(enriched_deals)
        
        logger.info(f"✅ Scan: {result['total']} Deals, {result['new']} neu")
        logger.info(f"📊 Price-Tracking: {price_stats['new_lowest']} neue Tiefstpreise")
        
        return result



    
    async def periodic_scan(self):
        """Periodischer Scan"""
        while True:
            try:
                await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
                await self.scan_deals()
            except Exception as e:
                logger.error(f"Scan-Fehler: {e}")
    
    async def start(self):
        """Starte Bot"""
        logger.info("🚀 Starte Offer Ghost Bot...")
        
        # Initialer Scan
        await self.scan_deals()
        
        # Bot Application
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Store bot instance
        self.bot = app.bot
        self.notifications = NotificationManager(self.bot)
        
        # Handlers
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("deals", self.cmd_deals))
        app.add_handler(CommandHandler("top", self.cmd_top))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("scan", self.cmd_scan))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("history", self.cmd_history))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_search))
        
        # Starte periodischen Scan
        self.scan_task = asyncio.create_task(self.periodic_scan())
        
        logger.info("⏰ Scheduler aktiv: Scan alle {}h".format(SCAN_INTERVAL_HOURS))
        logger.info("✅ Bot läuft!")
        
        # Run polling
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep running
        await asyncio.Event().wait()

# Health Check
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
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
        pass

def start_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("🏥 Health-Check Server läuft auf Port 8080")

# Main
if __name__ == "__main__":
    start_health_server()
    
    bot = OfferGhostBot()
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("👋 Bot gestoppt")
