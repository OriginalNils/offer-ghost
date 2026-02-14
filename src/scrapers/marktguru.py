import requests
import json
import os
from src.core.base_scraper import BaseScraper
from src.config import MARKTGURU_API_KEY, MARKTGURU_CLIENT_KEY, SEARCH_LIMIT
from src.core.utils import normalize_price
from src.core.ai_processor import extract_units_with_ai

class MarktguruScraper(BaseScraper):
    def __init__(self, zip_code, retailer_slug):
        super().__init__()
        self.zip_code = zip_code
        self.retailer_slug = retailer_slug
        # Die URL nutzt nun den dynamischen retailer_slug
        self.url = f"https://api.marktguru.de/api/v1/publishers/retailer/{self.retailer_slug}/offers?as=mobile&limit={SEARCH_LIMIT}&offset=0&zipCode={self.zip_code}"
        
        self.headers.update({
            "x-apikey": MARKTGURU_API_KEY,
            "x-clientkey": MARKTGURU_CLIENT_KEY,
            "Accept": "application/json",
            "Referer": "https://www.marktguru.de/"
        })

    def fetch_data(self):
        print(f"      [FETCH] Rufe {self.retailer_slug.upper()} für PLZ {self.zip_code} ab...")
        try:
            response = requests.get(self.url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            print(f"      [ERROR] {self.retailer_slug}: Status {response.status_code}")
            return None
        except Exception as e:
            print(f"      [ERROR] {self.retailer_slug}: {e}")
            return None

    def parse_data(self, raw_data):
        raw_items = raw_data.get('results') or []
        if not raw_items:
            return []

        # 1. Paket für KI vorbereiten
        ai_input = [{"id": i, "desc": item.get('description', '')} for i, item in enumerate(raw_items)]
        
        # 2. KI fragen
        print(f"      [AI] Analysiere {len(ai_input)} Einheiten mit Gemini...")
        ai_lookup = extract_units_with_ai(ai_input)

        # --- NEU: VORSCHAU-TABELLE KOPFZEILE ---
        print("\n      [VORSCHAU] KI-Extraktion & Grundpreis-Check (Top 10):")
        header = f"{'Produkt':<25} | {'Beschreibung':<25} | {'Extrakt':<12} | {'Grundpreis'}"
        print(f"      {header}")
        print("      " + "-" * 85)

        offers = []
        for i, item in enumerate(raw_items):
            ai_data = ai_lookup.get(i, {"amount": 1.0, "unit": "stk"})
            
            title = (item.get('product', {}).get('name') or item.get('title') or "Unbekannt")[:23]
            desc = (item.get('description', ''))[:23]
            price = item.get('price', 0.0)
            amount = ai_data.get('amount', 1.0)
            unit = ai_data.get('unit', 'stk')

            # Grundpreis berechnen
            unit_price = round(price / amount, 2) if amount and amount > 0 else price
            
            # Zeile für die Tabelle formatieren (nur für die ersten 10 Items)
            if i < 10:
                extracted = f"{amount} {unit}"
                u_price_str = f"{unit_price}€/{unit}"
                print(f"      {title:<25} | {desc:<25} | {extracted:<12} | {u_price_str}")

            offers.append({
                "title": item.get('product', {}).get('name', item.get('title')),
                "price": price,
                "unit_price": unit_price,
                "base_unit": unit,
                "description": item.get('description'),
                "store": self.retailer_slug.upper()
            })
        
        print("      " + "-" * 85 + "\n")
        return offers