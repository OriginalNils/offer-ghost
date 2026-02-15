import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class MarktguruScraper:
    """Scraper für Marktguru API"""
    
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
        self.client_key = client_key or "default"
        
    def fetch_deals(self, limit: int = 100) -> List[Dict]:
        """Hole Angebote"""
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
            
            logger.info(f"🔍 {self.store_name}: {len(raw_offers)} Angebote empfangen")
            
            # Debug: Erstes Angebot komplett loggen
            if raw_offers and logger.isEnabledFor(logging.DEBUG):
                import json
                logger.debug(f"Erstes Angebot JSON:\n{json.dumps(raw_offers[0], indent=2)}")
            
            # Parse alle Angebote
            deals = []
            for offer in raw_offers:
                deal = self._parse_offer(offer)
                if deal:
                    deals.append(deal)
            
            logger.info(f"✓ {self.store_name}: {len(deals)} Deals geparst")
            return deals
            
        except Exception as e:
            logger.error(f"❌ Fehler bei {self.store_name}: {e}")
            return []
    
    def _parse_offer(self, offer: Dict) -> Optional[Dict]:
        """Parse ein einzelnes Angebot - robuster"""
        try:
            # Name kann in verschiedenen Feldern sein
            name = (
                offer.get("name") or 
                offer.get("title") or 
                offer.get("productName") or
                offer.get("description", "")[:50]
            )
            
            if not name or name == "":
                logger.debug(f"Überspringe Angebot ohne Namen: {offer.get('id')}")
                return None
            
            name = str(name).strip()
            
            # Beschreibung
            description = str(offer.get("description", "")).strip()
            
            # Preis (verschiedene Feldnamen möglich)
            price = offer.get("price") or offer.get("currentPrice") or 0
            
            # Base-Price (optional - oft bei Angeboten nicht vorhanden)
            base_price = offer.get("basePrice") or offer.get("originalPrice") or offer.get("oldPrice")
            
            # Rabatt berechnen
            discount_percent = 0
            saved_amount = 0
            
            if base_price and base_price > price:
                discount_percent = round(((base_price - price) / base_price) * 100)
                saved_amount = round(base_price - price, 2)
            
            # ALLE Marktguru-Angebote SIND Deals - auch ohne expliziten basePrice
            # Setze min. 1% wenn kein basePrice vorhanden
            if discount_percent == 0:
                discount_percent = 1  # Marker dass es ein Angebot ist
            
            # Gültigkeit
            valid_from = offer.get("validFrom", "")
            valid_until = offer.get("validUntil", "")
            
            days_left = None
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
                "price": float(price) if price else 0,
                "base_price": float(base_price) if base_price else None,
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
            logger.debug(f"Parse-Fehler: {e} | Offer-ID: {offer.get('id')}")
            return None
    
    def _guess_category(self, name: str, desc: str) -> str:
        """Kategorie-Zuordnung"""
        text = (name + " " + desc).lower()
        
        categories = {
            "Obst & Gemüse": ["obst", "gemüse", "salat", "tomate", "gurke", "apfel", "banane", "kartoffel", "zwiebel"],
            "Fleisch & Fisch": ["fleisch", "wurst", "hack", "schnitzel", "steak", "fisch", "lachs", "hähnchen"],
            "Milchprodukte & Eier": ["milch", "käse", "joghurt", "butter", "quark", "ei", "sahne", "frischkäse"],
            "Getränke": ["cola", "saft", "wasser", "bier", "wein", "limo", "getränk", "kaffee", "tee", "radler"],
            "Süßes & Snacks": ["schoko", "süß", "chips", "keks", "gummi", "bonbon", "snack", "riegel", "pralinen"],
            "Brot & Backwaren": ["brot", "brötchen", "kuchen", "toast", "croissant"],
            "Tiefkühl": ["tiefkühl", "pizza", "eis", "frost"],
            "Konserven & Vorrat": ["dose", "konserve", "pasta", "reis", "mehl", "nudel"],
            "Haushalt & Drogerie": ["putzmittel", "waschmittel", "shampoo", "seife", "creme", "duschgel", "zahnpasta"],
        }
        
        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category
        
        return "Sonstiges"
    
    def _extract_amount(self, desc: str) -> str:
        """Mengenangabe extrahieren"""
        import re
        
        if not desc:
            return ""
        
        patterns = [
            r'(\d+[,.]?\d*\s*(?:kg|g|l|ml|stk|st\.))',
            r'(\d+\s*x\s*\d+[,.]?\d*\s*(?:kg|g|l|ml))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
