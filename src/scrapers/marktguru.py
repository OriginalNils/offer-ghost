import requests
import json
import logging
from src.core.base_scraper import BaseScraper
from src.core.ai_processor import extract_units_with_ai
from src.core.utils import rate_limit, calculate_unit_price, clean_product_name
from src.config import (
    MARKTGURU_API_KEY, 
    MARKTGURU_CLIENT_KEY, 
    SEARCH_LIMIT,
    STORES_CONFIG
)

logger = logging.getLogger(__name__)


class MarktguruScraper(BaseScraper):
    def __init__(self, zip_code, retailer_slug):
        logger.debug(f"=== MarktguruScraper.__init__() für {retailer_slug} ===")
        super().__init__()
        self.zip_code = zip_code
        self.retailer_slug = retailer_slug
        self.store_name = STORES_CONFIG['stores'].get(retailer_slug, {}).get('name', retailer_slug.upper())
        
        logger.debug(f"Store: {self.store_name} ({retailer_slug})")
        logger.debug(f"PLZ: {zip_code}")
        
        self.url = (
            f"https://api.marktguru.de/api/v1/publishers/retailer/"
            f"{self.retailer_slug}/offers?as=mobile&limit={SEARCH_LIMIT}"
            f"&offset=0&zipCode={self.zip_code}"
        )
        
        logger.debug(f"API-URL: {self.url}")
        
        self.headers.update({
            "x-apikey": MARKTGURU_API_KEY,
            "x-clientkey": MARKTGURU_CLIENT_KEY,
            "Accept": "application/json",
            "Referer": "https://www.marktguru.de/",
            "Origin": "https://www.marktguru.de",
        })
        
        logger.debug(f"Headers konfiguriert (API-Key: {MARKTGURU_API_KEY[:10]}...)")

    @rate_limit(calls_per_second=2)
    def fetch_data(self):
        """Holt Angebote von der Marktguru-API mit Rate Limiting."""
        logger.debug(f"=== fetch_data() für {self.store_name} ===")
        self.logger.info(f"Rufe {self.store_name} für PLZ {self.zip_code} ab...")
        
        try:
            logger.debug("Sende HTTP GET Request...")
            response = requests.get(self.url, headers=self.headers, timeout=10)
            
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"JSON erhalten, Keys: {list(data.keys())}")
                logger.debug(f"Anzahl Results: {len(data.get('results', []))}")
                return data
            else:
                self.logger.error(f"HTTP {response.status_code} für {self.store_name}")
                logger.debug(f"Response Text: {response.text[:500]}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout bei {self.store_name}")
            return None
        except Exception as e:
            self.logger.error(f"Fehler bei {self.store_name}: {e}", exc_info=True)
            return None

    def parse_data(self, raw_data):
        """Verarbeitet API-Daten mit AI-Unterstützung."""
        logger.debug(f"=== parse_data() für {self.store_name} ===")
        
        raw_items = raw_data.get('results') or []
        logger.debug(f"Rohe Items: {len(raw_items)}")
        
        if not raw_items:
            self.logger.warning(f"Keine Items für {self.store_name} gefunden")
            return []
        
        if raw_items:
            logger.info("=== DEBUG: Erstes Raw-Item ===")
            logger.info(json.dumps(raw_items[0], indent=2, ensure_ascii=False))
            logger.info("===============================")

        # 1. Daten für AI vorbereiten
        logger.debug("Bereite AI-Input vor...")
        ai_input = [
            {"id": i, "desc": item.get('description', '')} 
            for i, item in enumerate(raw_items)
        ]
        logger.debug(f"AI-Input: {len(ai_input)} Items")
        logger.debug(f"Erste 2 Items: {ai_input[:2]}")
        
        # 2. AI-Analyse durchführen
        self.logger.info(f"Analysiere {len(ai_input)} Items mit AI...")
        
        try:
            ai_lookup = extract_units_with_ai(ai_input)
            logger.debug(f"AI-Lookup erhalten: {len(ai_lookup)} Einträge")
        except Exception as e:
            logger.error(f"✗ AI-Aufruf fehlgeschlagen: {e}", exc_info=True)
            raise

        # 3. Terminal-Vorschau vorbereiten
        self._print_preview_header()

        offers = []
        for i, item in enumerate(raw_items):
            logger.debug(f"--- Verarbeite Item {i} ---")
            
            # AI-Daten abrufen (mit Fallback)
            ai_data = ai_lookup.get(i) or ai_lookup.get(str(i)) or {
                "amount": 1.0, 
                "unit": "stk",  # ← Default
                "category": "Sonstiges"
            }
            logger.debug(f"AI-Daten für Item {i}: {ai_data}")
            
            # Daten extrahieren und normalisieren
            amount = ai_data.get('amount') or 1.0
            unit = ai_data.get('unit') or 'stk'
            category = ai_data.get('category') or 'Sonstiges'
            
            price = item.get('price', 0.0)
            title_raw = (
                item.get('product', {}).get('name') or 
                item.get('title') or 
                "Unbekannt"
            )
            title = clean_product_name(title_raw)
            
            logger.debug(f"Item {i}: {title} | {price}€ | {amount} {unit}")
            
            # Grundpreis berechnen
            unit_price = calculate_unit_price(price, amount, unit)

            # Terminal-Vorschau (nur erste 10)
            if i < 10:
                self._print_preview_row(title, category, amount, unit, unit_price)

            # Angebot zur Liste hinzufügen
            offers.append({
                "title": title,
                "category": category,
                "price": price,
                "unit_price": unit_price,
                "base_unit": unit,
                "amount": amount,
                "description": item.get('description', ''),
                "brand": item.get('brand', {}).get('name', ''),
                "store": self.store_name,
                "store_slug": self.retailer_slug,
                "valid_until": item.get('validTo', '')
            })
        
        self._print_preview_footer()
        logger.debug(f"Parse-Ergebnis: {len(offers)} Angebote")
        return offers

    def _print_preview_header(self):
        """Druckt Tabellenkopf für Terminal-Vorschau."""
        print(f"\n      [VORSCHAU] {self.store_name} Analyse (Top 10):")
        header = f"{'Produkt':<25} | {'Kategorie':<18} | {'Menge':<10} | {'Grundpreis'}"
        print(f"      {header}")
        print("      " + "-" * 85)

    def _print_preview_row(self, title, category, amount, unit, unit_price):
        """Druckt eine Zeile der Terminal-Vorschau."""
        short_title = title[:23]
        short_cat = category[:18]
        amount_str = f"{amount} {unit}"
        price_str = f"{unit_price}€/{unit}"
        print(f"      {short_title:<25} | {short_cat:<18} | {amount_str:<10} | {price_str}")

    def _print_preview_footer(self):
        """Druckt Tabellenfußzeile."""
        print("      " + "-" * 85 + "\n")
