import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class MarktguruScraper:
    """Scraper für Marktguru API - nur echte Deals"""
    
    BASE_URL = "https://api.marktguru.de/api/v1/publishers/retailer/{store}/offers"
    
    STORE_NAMES = {
        "rewe": "REWE",
        "lidl": "Lidl",
        "aldi-sued": "Aldi Süd",
        "kaufland": "Kaufland",
        "edeka": "EDEKA",
        "penny": "Penny"
    }
    
    def __init__(self, store: str, zip_code: str, api_key: str, client_key: str = ""):
        self.store = store
        self.store_name = self.STORE_NAMES.get(store, store.upper())
        self.zip_code = zip_code
        self.api_key = api_key
        self.client_key = client_key or "default-client-key"  # Fallback
        
    def fetch_deals(self, limit: int = 100) -> List[Dict]:
        """Hole nur echte Deals (mit Rabatt)"""
        url = self.BASE_URL.format(store=self.store)
        
        headers = {
            "x-apikey": self.api_key,
            "x-clientkey": self.client_key,
            "Accept": "application/json",
            "Referer": "https://www.marktguru.de/",
            "Origin": "https://www.marktguru.de",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"
        }
        
        params = {
            "as": "mobile",
            "limit": limit,
            "offset": 0,
            "zipCode": self.zip_code
        }
        
        try:
            logger.info(f"📡 Scraping {self.store_name}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            raw_offers = data.get("results", [])
            
            # Parse & filter nur echte Deals
            deals = []
            for offer in raw_offers:
                deal = self._parse_offer(offer)
                if deal and deal.get("discount_percent", 0) > 0:
                    deals.append(deal)
            
            logger.info(f"✓ {self.store_name}: {len(deals)} Deals gefunden")
            return deals
            
        except Exception as e:
            logger.error(f"❌ Fehler bei {self.store_name}: {e}")
            return []
    
    def _parse_offer(self, offer: Dict) -> Optional[Dict]:
        """Parse ein einzelnes Angebot"""
        try:
            # Basis-Daten
            name = offer.get("name", "").strip()
            description = offer.get("description", "").strip()
            
            if not name:
                return None
            
            # Preise
            price = offer.get("price")
            base_price = offer.get("basePrice")
            
            # Rabatt berechnen
            discount_percent = 0
            saved_amount = 0
            
            if price and base_price and base_price > price:
                discount_percent = round(((base_price - price) / base_price) * 100)
                saved_amount = round(base_price - price, 2)
            
            # Gültigkeit
            valid_from = offer.get("validFrom", "")
            valid_until = offer.get("validUntil", "")
            
            days_left = 0
            if valid_until:
                try:
                    end_date = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                    days_left = (end_date - datetime.now(end_date.tzinfo)).days
                except:
                    pass
            
            # Kategorie
            category = self._guess_category(name, description)
            
            # Menge
            amount_str = self._extract_amount(description)
            
            return {
                "id": offer.get("id"),
                "name": name,
                "description": description,
                "price": price,
                "base_price": base_price,
                "discount_percent": discount_percent,
                "saved_amount": saved_amount,
                "amount": amount_str,
                "category": category,
                "store": self.store_name,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "days_left": days_left,
                "image_url": offer.get("imageUrl", ""),
                "scraped_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"Parse-Fehler: {e}")
            return None
    
    def _guess_category(self, name: str, desc: str) -> str:
        """Einfache Kategorie-Zuordnung"""
        text = (name + " " + desc).lower()
        
        if any(x in text for x in ["obst", "gemüse", "salat", "tomate", "gurke", "apfel", "banane", "kartoffel"]):
            return "Obst & Gemüse"
        elif any(x in text for x in ["fleisch", "wurst", "hack", "schnitzel", "steak", "fisch", "lachs"]):
            return "Fleisch & Fisch"
        elif any(x in text for x in ["milch", "käse", "joghurt", "butter", "quark", "ei", "sahne"]):
            return "Milchprodukte & Eier"
        elif any(x in text for x in ["cola", "saft", "wasser", "bier", "wein", "limo", "getränk", "kaffee", "tee"]):
            return "Getränke"
        elif any(x in text for x in ["schoko", "süß", "chips", "keks", "gummi", "bonbon", "snack", "riegel"]):
            return "Süßes & Snacks"
        elif any(x in text for x in ["brot", "brötchen", "kuchen", "toast", "croissant"]):
            return "Brot & Backwaren"
        elif any(x in text for x in ["tiefkühl", "pizza", "eis", "frost"]):
            return "Tiefkühl"
        elif any(x in text for x in ["dose", "konserve", "pasta", "reis", "mehl", "nudel"]):
            return "Konserven & Vorrat"
        elif any(x in text for x in ["putzmittel", "waschmittel", "shampoo", "seife", "creme", "duschgel"]):
            return "Haushalt & Drogerie"
        else:
            return "Sonstiges"
    
    def _extract_amount(self, desc: str) -> str:
        """Extrahiere Mengenangabe"""
        import re
        
        patterns = [
            r'(\d+[,.]?\d*\s*(?:kg|g|l|ml|stk|st\.))',
            r'(\d+\s*x\s*\d+[,.]?\d*\s*(?:kg|g|l|ml))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
