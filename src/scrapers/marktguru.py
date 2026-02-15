import requests
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class MarktguruScraper:
    """Scraper für Marktguru API mit vollständigem Debug-Logging"""
    
    BASE_URL = "https://api.marktguru.de/api/v1/publishers/retailer/{store}/offers"
    
    STORE_NAMES = {
        "rewe": "REWE",
        "lidl": "Lidl",
        "aldi-sued": "Aldi Süd",
        "kaufland": "Kaufland",
        "edeka": "EDEKA",
        "penny": "Penny"
    }
    
    def __init__(self, store: str, zip_code: str, api_key: str, client_key: str = "", debug_mode: bool = False):
        self.store = store
        self.store_name = self.STORE_NAMES.get(store, store.upper())
        self.zip_code = zip_code
        self.api_key = api_key
        self.client_key = client_key or "default"
        self.debug_mode = debug_mode
        
        if self.debug_mode:
            logger.info(f"🔍 DEBUG: Scraper initialisiert für {self.store_name}")
            logger.debug(f"  API-Key: {self.api_key[:10]}...")
            logger.debug(f"  Client-Key: {self.client_key[:10]}...")
            logger.debug(f"  PLZ: {self.zip_code}")
    
    def fetch_deals(self, limit: int = 100) -> List[Dict]:
        """Hole Angebote mit vollständigem Debug-Logging"""
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
            
            if self.debug_mode:
                logger.debug(f"🔍 REQUEST:")
                logger.debug(f"  URL: {url}")
                logger.debug(f"  Params: {params}")
                logger.debug(f"  Headers: {json.dumps({k: v[:20]+'...' if len(v) > 20 else v for k, v in headers.items()}, indent=2)}")
            
            # Request
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if self.debug_mode:
                logger.debug(f"🔍 RESPONSE:")
                logger.debug(f"  Status: {response.status_code}")
                logger.debug(f"  Headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            data = response.json()
            raw_offers = data.get("results", [])
            
            logger.info(f"🔍 {self.store_name}: {len(raw_offers)} Angebote empfangen")
            
            # Debug: Save raw response
            if self.debug_mode:
                self._save_debug_data(f"{self.store}_raw_response.json", data)
                
                # Log first offer completely
                if raw_offers:
                    logger.debug(f"🔍 ERSTES ANGEBOT (komplett):")
                    logger.debug(json.dumps(raw_offers[0], indent=2, ensure_ascii=False))
                    
                    # Log available fields
                    logger.debug(f"🔍 VERFÜGBARE FELDER im Angebot:")
                    for key in raw_offers[0].keys():
                        value = raw_offers[0][key]
                        value_type = type(value).__name__
                        value_preview = str(value)[:50] if value else "None"
                        logger.debug(f"  • {key} ({value_type}): {value_preview}")
            
            # Parse
            deals = []
            parse_stats = {
                "total": len(raw_offers),
                "parsed": 0,
                "skipped_no_name": 0,
                "skipped_no_discount": 0,
                "errors": 0
            }
            
            for idx, offer in enumerate(raw_offers):
                deal = self._parse_offer(offer, idx)
                
                if deal:
                    deals.append(deal)
                    parse_stats["parsed"] += 1
                    
                    if self.debug_mode and idx < 3:  # Log erste 3 geparste Deals
                        logger.debug(f"🔍 PARSED DEAL #{idx+1}:")
                        logger.debug(f"  Name: {deal['name']}")
                        logger.debug(f"  Preis: {deal['price']}€ (war: {deal['base_price']}€)")
                        logger.debug(f"  Rabatt: {deal['discount_percent']}%")
                        logger.debug(f"  Kategorie: {deal['category']}")
                        logger.debug(f"  Menge: {deal['amount']}")
            
            # Stats
            logger.info(f"✓ {self.store_name}: {len(deals)} Deals geparst")
            
            if self.debug_mode:
                logger.debug(f"🔍 PARSE-STATISTIK {self.store_name}:")
                logger.debug(f"  Total Angebote: {parse_stats['total']}")
                logger.debug(f"  Erfolgreich geparst: {parse_stats['parsed']}")
                logger.debug(f"  Ohne Namen: {parse_stats['skipped_no_name']}")
                logger.debug(f"  Ohne Rabatt: {parse_stats['skipped_no_discount']}")
                logger.debug(f"  Fehler: {parse_stats['errors']}")
                
                # Save parsed deals
                self._save_debug_data(f"{self.store}_parsed_deals.json", deals)
            
            return deals
            
        except Exception as e:
            logger.error(f"❌ Fehler bei {self.store_name}: {e}")
            if self.debug_mode:
                logger.exception("🔍 FULL STACK TRACE:")
            return []
    
    def _parse_offer(self, offer: Dict, idx: int = 0) -> Optional[Dict]:
        """Parse mit Debug-Logging"""
        try:
            # Name aus verschiedenen Feldern
            name = offer.get("name") or offer.get("title") or ""
            description = str(offer.get("description", "")).strip()
            
            # Fallback: Erste Zeile als Name
            if not name and description:
                lines = description.split('\n')
                name = lines[0].strip() if lines else ""
                description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
            
            if not name:
                if self.debug_mode and idx < 3:
                    logger.debug(f"🔍 Angebot #{idx}: Überspringe (kein Name)")
                    logger.debug(f"  Verfügbare Felder: {list(offer.keys())}")
                return None
            
            # Preise
            price = offer.get("price") or offer.get("currentPrice") or 0
            base_price = offer.get("basePrice") or offer.get("originalPrice") or offer.get("oldPrice")
            
            if self.debug_mode and idx < 3:
                logger.debug(f"🔍 Angebot #{idx} Preise:")
                logger.debug(f"  price: {price}")
                logger.debug(f"  basePrice: {base_price}")
                logger.debug(f"  Alle Preis-Felder: {[k for k in offer.keys() if 'price' in k.lower()]}")
            
            # Rabatt
            discount_percent = 0
            saved_amount = 0
            
            if base_price and base_price > price:
                discount_percent = round(((base_price - price) / base_price) * 100)
                saved_amount = round(base_price - price, 2)
            
            if discount_percent == 0:
                if self.debug_mode and idx < 3:
                    logger.debug(f"🔍 Angebot #{idx}: Kein Rabatt (überspringe)")
                return None
            
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
            if self.debug_mode:
                logger.debug(f"🔍 Parse-Fehler bei Angebot #{idx}: {e}")
                logger.debug(f"  Offer-Daten: {json.dumps(offer, indent=2, ensure_ascii=False)[:500]}")
            return None
    
    def _save_debug_data(self, filename: str, data):
        """Speichere Debug-Daten"""
        try:
            from config import DEBUG_DIR
            filepath = DEBUG_DIR / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"💾 Debug-Daten gespeichert: {filepath}")
        except Exception as e:
            logger.debug(f"Fehler beim Speichern von Debug-Daten: {e}")
    
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
            r'(\d+[,.]?\d*\s*(?:kg|g|l|ml|stk|st\.|stück))',
            r'(\d+\s*x\s*\d+[,.]?\d*\s*(?:kg|g|l|ml))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
