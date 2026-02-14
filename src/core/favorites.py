"""
Favoriten/Watchlist System für Offer Ghost.
"""

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FavoritesManager:
    """Verwaltet Favoriten/Watchlist."""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.favorites_file = os.path.join(data_dir, "favorites.json")
        self.favorites = self._load_favorites()
        
        logger.info(f"FavoritesManager initialisiert: {len(self.favorites)} Favoriten")
    
    def _load_favorites(self):
        """Lädt Favoriten aus JSON."""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden von Favoriten: {e}")
                return []
        return []
    
    def _save_favorites(self):
        """Speichert Favoriten als JSON."""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Speichern von Favoriten: {e}")
    
    def add_favorite(self, product_id, user_note=""):
        """Fügt Produkt zu Favoriten hinzu."""
        # Prüfe ob bereits vorhanden
        if any(f['product_id'] == product_id for f in self.favorites):
            logger.info(f"Produkt {product_id} ist bereits Favorit")
            return False
        
        favorite = {
            'product_id': product_id,
            'added_at': datetime.now().isoformat(),
            'user_note': user_note,
            'notifications_enabled': True
        }
        
        self.favorites.append(favorite)
        self._save_favorites()
        
        logger.info(f"Produkt {product_id} zu Favoriten hinzugefügt")
        return True
    
    def remove_favorite(self, product_id):
        """Entfernt Produkt aus Favoriten."""
        initial_count = len(self.favorites)
        self.favorites = [f for f in self.favorites if f['product_id'] != product_id]
        
        if len(self.favorites) < initial_count:
            self._save_favorites()
            logger.info(f"Produkt {product_id} aus Favoriten entfernt")
            return True
        
        logger.warning(f"Produkt {product_id} war nicht in Favoriten")
        return False
    
    def is_favorite(self, product_id):
        """Prüft ob Produkt Favorit ist."""
        return any(f['product_id'] == product_id for f in self.favorites)
    
    def get_all_favorites(self):
        """Gibt alle Favoriten zurück."""
        return self.favorites
    
    def get_favorite_ids(self):
        """Gibt nur die Produkt-IDs zurück."""
        return [f['product_id'] for f in self.favorites]
    
    def update_note(self, product_id, note):
        """Aktualisiert Notiz für Favorit."""
        for favorite in self.favorites:
            if favorite['product_id'] == product_id:
                favorite['user_note'] = note
                self._save_favorites()
                logger.info(f"Notiz für {product_id} aktualisiert")
                return True
        return False
    
    def toggle_notifications(self, product_id):
        """Schaltet Benachrichtigungen für Favorit um."""
        for favorite in self.favorites:
            if favorite['product_id'] == product_id:
                favorite['notifications_enabled'] = not favorite.get('notifications_enabled', True)
                self._save_favorites()
                return favorite['notifications_enabled']
        return False
    
    def get_favorites_with_details(self, tracker):
        """Gibt Favoriten mit vollständigen Produkt-Details zurück."""
        detailed_favorites = []
        
        for favorite in self.favorites:
            product_id = favorite['product_id']
            
            if product_id not in tracker.products:
                continue
            
            product = tracker.products[product_id]
            brand = tracker.brands.get(product['brand_id'], {})
            
            # Aktuelle Preise von allen Stores
            current_prices = {}
            if product_id in tracker.price_history:
                today = datetime.now().strftime("%Y-%m-%d")
                
                for store, history in tracker.price_history[product_id].items():
                    if history and history[-1]['date'] == today:
                        latest = history[-1]
                        current_prices[store] = {
                            'price': latest['price'],
                            'unit_price': latest['unit_price'],
                            'valid_until': latest.get('valid_until', '')
                        }
            
            # Berechne besten Preis
            best_price = None
            best_store = None
            if current_prices:
                best_store = min(current_prices.items(), key=lambda x: x[1]['unit_price'])
                best_price = best_store[1]['unit_price']
                best_store = best_store[0]
            
            detailed_favorites.append({
                'product_id': product_id,
                'name': product['name'],
                'brand': brand.get('name', ''),
                'category': product['category'],
                'base_unit': product['base_unit'],
                'current_prices': current_prices,
                'best_price': best_price,
                'best_store': best_store,
                'stores_available': product['stores_available'],
                'added_at': favorite['added_at'],
                'user_note': favorite.get('user_note', ''),
                'notifications_enabled': favorite.get('notifications_enabled', True)
            })
        
        return detailed_favorites
