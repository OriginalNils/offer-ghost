import logging
from typing import List, Dict
from telegram import Bot

logger = logging.getLogger(__name__)

class NotificationManager:
    """Verwaltet Push-Notifications"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.enabled_users = set()
    
    def enable(self, user_id: int):
        """Aktiviere Notifications für User"""
        self.enabled_users.add(user_id)
        logger.info(f"🔔 User {user_id}: Notifications ON")
    
    def disable(self, user_id: int):
        """Deaktiviere Notifications"""
        self.enabled_users.discard(user_id)
        logger.info(f"🔕 User {user_id}: Notifications OFF")
    
    def is_enabled(self, user_id: int) -> bool:
        """Check ob Notifications aktiv"""
        return user_id in self.enabled_users
    
    async def notify_new_deals(self, user_id: int, deals: List[Dict], favorite_matches: List[Dict]):
        """Sende Notification über neue Deals"""
        if not self.is_enabled(user_id):
            return
        
        try:
            # Favoriten-Matches zuerst
            if favorite_matches:
                msg = "🎯 <b>Neue Deals zu deinen Favoriten!</b>\n\n"
                for deal in favorite_matches[:5]:  # Max 5
                    msg += self._format_deal_short(deal) + "\n\n"
                await self.bot.send_message(user_id, msg, parse_mode="HTML")
            
            # Allgemeine neue Deals
            if deals and len(deals) > len(favorite_matches):
                other_deals = [d for d in deals if d not in favorite_matches]
                if other_deals:
                    msg = f"🔥 <b>{len(other_deals)} neue Deals verfügbar!</b>\n\n"
                    msg += f"Nutze /deals um alle zu sehen."
                    await self.bot.send_message(user_id, msg, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Notification-Fehler für User {user_id}: {e}")
    
    def _format_deal_short(self, deal: Dict) -> str:
        """Kurz-Format für Notifications"""
        emoji = self._get_category_emoji(deal.get("category", ""))
        
        text = f"{emoji} <b>{deal['name']}</b>\n"
        text += f"💰 {deal['price']:.2f}€"
        
        if deal.get("base_price"):
            text += f" <s>{deal['base_price']:.2f}€</s>"
        
        text += f" (-{deal['discount_percent']}%)\n"
        text += f"🏪 {deal['store']}"
        
        return text
    
    def _get_category_emoji(self, category: str) -> str:
        """Hole Emoji für Kategorie"""
        from src.config import CATEGORY_EMOJIS
        return CATEGORY_EMOJIS.get(category, "📦")
