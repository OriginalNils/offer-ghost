import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

class PriceTracker:
    """Trackt Preise über Zeit für alle Produkte"""
    
    def __init__(self, price_history_file: Path):
        self.price_history_file = price_history_file
        self.history = self._load()
    
    def _load(self) -> Dict:
        """Lade Preis-Historie"""
        if self.price_history_file.exists():
            try:
                with open(self.price_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden von price_history: {e}")
        
        return {
            "products": {},  # {product_key: {...}}
            "last_update": None
        }
    
    def _save(self):
        """Speichere Preis-Historie"""
        self.history["last_update"] = datetime.now().isoformat()
        with open(self.price_history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def _get_product_key(self, deal: Dict) -> str:
        """Erstelle eindeutigen Product-Key"""
        # Kombination aus Name + Store (gleiches Produkt kann bei verschiedenen Stores sein)
        name = deal.get("name", "").lower().strip()
        store = deal.get("store", "").lower().strip()
        # Optional: Brand einbeziehen für mehr Präzision
        brand = deal.get("brand", "").lower().strip()
        
        if brand:
            return f"{store}_{brand}_{name}"
        return f"{store}_{name}"
    
    def update_prices(self, deals: List[Dict]) -> Dict:
        """Update Preis-Historie mit neuen Deals"""
        stats = {
            "tracked": 0,
            "new_products": 0,
            "new_lowest": 0,
            "new_highest": 0
        }
        
        now = datetime.now().isoformat()
        
        for deal in deals:
            product_key = self._get_product_key(deal)
            price = deal.get("price", 0)
            
            if price <= 0:
                continue
            
            # Neues Produkt
            if product_key not in self.history["products"]:
                self.history["products"][product_key] = {
                    "name": deal.get("name"),
                    "brand": deal.get("brand"),
                    "store": deal.get("store"),
                    "first_seen": now,
                    "last_seen": now,
                    "prices": [],
                    "lowest_price": price,
                    "highest_price": price,
                    "avg_price": price,
                    "last_offer_date": now if deal.get("offer_type") else None,
                    "offer_count": 1 if deal.get("offer_type") else 0
                }
                stats["new_products"] += 1
            
            product = self.history["products"][product_key]
            
            # Preis-Entry hinzufügen
            price_entry = {
                "price": price,
                "date": now,
                "offer_type": deal.get("offer_type", "offer"),
                "discount_percent": deal.get("discount_percent", 0),
                "base_price": deal.get("base_price")
            }
            
            product["prices"].append(price_entry)
            product["last_seen"] = now
            
            # Offer-Tracking
            if deal.get("offer_type"):
                product["last_offer_date"] = now
                product["offer_count"] = product.get("offer_count", 0) + 1
            
            # Min/Max/Avg updaten
            if price < product["lowest_price"]:
                product["lowest_price"] = price
                stats["new_lowest"] += 1
            
            if price > product["highest_price"]:
                product["highest_price"] = price
                stats["new_highest"] += 1
            
            # Durchschnitt neu berechnen (letzte 30 Tage)
            recent_prices = [p["price"] for p in product["prices"][-30:]]
            product["avg_price"] = round(sum(recent_prices) / len(recent_prices), 2)
            
            # Alte Einträge löschen (>90 Tage)
            cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()
            product["prices"] = [p for p in product["prices"] if p["date"] >= cutoff_date]
            
            stats["tracked"] += 1
        
        self._save()
        
        logger.info(f"📊 Price-Tracking: {stats['tracked']} Produkte, {stats['new_products']} neu, {stats['new_lowest']} neue Tiefstpreise")
        
        return stats
    
    def enrich_deal(self, deal: Dict) -> Dict:
        """Reichere Deal mit Preis-Historie an"""
        product_key = self._get_product_key(deal)
        
        if product_key not in self.history["products"]:
            return deal
        
        product = self.history["products"][product_key]
        current_price = deal.get("price", 0)
        
        # Preis-Analyse
        deal["price_history"] = {
            "lowest_price": product["lowest_price"],
            "highest_price": product["highest_price"],
            "avg_price": product["avg_price"],
            "is_lowest": current_price <= product["lowest_price"],
            "is_highest": current_price >= product["highest_price"],
            "vs_avg": round(((current_price - product["avg_price"]) / product["avg_price"]) * 100, 1) if product["avg_price"] > 0 else 0,
            "offer_count": product.get("offer_count", 0),
            "first_seen": product["first_seen"]
        }
        
        # Letztes Angebot
        if product.get("last_offer_date"):
            last_offer = datetime.fromisoformat(product["last_offer_date"])
            days_since = (datetime.now() - last_offer).days
            
            deal["price_history"]["last_offer_days_ago"] = days_since
        
        # Trend (letzte 7 Preise)
        if len(product["prices"]) >= 3:
            recent = product["prices"][-7:]
            prices = [p["price"] for p in recent]
            
            if len(prices) >= 3:
                # Simple Trend-Erkennung
                first_half = sum(prices[:len(prices)//2]) / (len(prices)//2)
                second_half = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)
                
                if second_half < first_half * 0.95:
                    deal["price_history"]["trend"] = "falling"
                elif second_half > first_half * 1.05:
                    deal["price_history"]["trend"] = "rising"
                else:
                    deal["price_history"]["trend"] = "stable"
        
        return deal
    
    def get_product_history(self, product_key: str) -> Optional[Dict]:
        """Hole komplette Historie eines Produkts"""
        return self.history["products"].get(product_key)
    
    def get_stats(self) -> Dict:
        """Statistiken"""
        return {
            "total_products": len(self.history["products"]),
            "total_price_points": sum(len(p["prices"]) for p in self.history["products"].values()),
            "last_update": self.history.get("last_update")
        }
