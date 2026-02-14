import requests
import json
import os
from src.core.base_scraper import BaseScraper
from src.config import MARKTGURU_API_KEY, MARKTGURU_CLIENT_KEY, SEARCH_LIMIT
from src.core.utils import normalize_price

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
        offers = []
        items = raw_data.get('results') or []
        
        for item in items:
            # Wir nehmen den Namen, den die API liefert oder unseren Slug
            desc = item.get('description', '')
            price = item.get('price', 0.0)
            unit_price, base_unit = normalize_price(desc, price)

            
            offers.append({
                "title": item.get('product', {}).get('name', item.get('title', 'Unbekannt')),
                "price": item.get('price'),
                "unit_price": unit_price, # NEU: 12.45
                "base_unit": base_unit,   # NEU: "kg"
                "description": item.get('description'),
                "brand": item.get('brand', {}).get('name', ''),
                "store": item.get('retailer', {}).get('name', self.retailer_slug.upper()),
                "valid_until": item.get('validTo')
            })
        return offers