import json
import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ProductTracker:
    """
    Verwaltet Produkte, Marken und Preisverlauf.
    Dedupliziert ähnliche Produkte und normalisiert Marken.
    """
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.products_dir = os.path.join(data_dir, "products")
        
        # Pfade
        self.products_file = os.path.join(self.products_dir, "products.json")
        self.brands_file = os.path.join(self.products_dir, "brands.json")
        self.price_history_file = os.path.join(self.products_dir, "price_history.json")
        
        # Verzeichnis erstellen
        os.makedirs(self.products_dir, exist_ok=True)
        
        # Daten laden
        self.products = self._load_json(self.products_file, {})
        self.brands = self._load_json(self.brands_file, {})
        self.price_history = self._load_json(self.price_history_file, {})
        
        logger.info(f"ProductTracker initialisiert: {len(self.products)} Produkte, {len(self.brands)} Marken")
    
    def _load_json(self, filepath, default):
        """Lädt JSON-Datei oder gibt Default zurück."""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden von {filepath}: {e}")
                return default
        return default
    
    def _save_json(self, filepath, data):
        """Speichert Daten als JSON."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Speichern von {filepath}: {e}")
    
    def _normalize_text(self, text):
        """Normalisiert Text für Vergleiche."""
        if not text:
            return ""
        return text.lower().strip()
    
    def _similarity(self, str1, str2):
        """Berechnet Ähnlichkeit zwischen zwei Strings (0-1)."""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _generate_product_id(self, name, brand):
        """Generiert eindeutige Produkt-ID."""
        combined = f"{self._normalize_text(name)}_{self._normalize_text(brand)}"
        return "prod_" + hashlib.md5(combined.encode()).hexdigest()[:10]
    
    def _parse_date(self, date_str):
        """Parst Datum-String zu datetime (unterstützt ISO-Format)."""
        if not date_str:
            return None
        
        try:
            # ISO-Format mit Timestamp: "2026-02-14T22:59:59Z"
            if 'T' in date_str:
                # Parse als ISO und konvertiere zu lokalem Datum (ohne Timezone)
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Entferne Timezone-Info für einfacheren Vergleich
                return dt.replace(tzinfo=None)
            else:
                # Einfaches Datum: "2026-02-14"
                return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Konnte Datum nicht parsen: {date_str} - {e}")
            return None


    def _days_until_expiry(self, valid_until):
        """Berechnet Tage bis Ablauf."""
        expiry = self._parse_date(valid_until)
        if not expiry:
            return None
        
        now = datetime.now()  # Jetzt timezone-naive
        
        # Setze Uhrzeit auf Ende des Tages für fairen Vergleich
        expiry_date = expiry.replace(hour=23, minute=59, second=59)
        
        delta = expiry_date - now
        return delta.days
    
    def get_or_create_brand(self, brand_name):
        """
        Findet existierende Marke oder erstellt neue.
        Nutzt Fuzzy-Matching für ähnliche Marken.
        """
        # Leere Marken → None
        if not brand_name or brand_name.strip() == "" or brand_name == "thisisnobrand123":
            return None
        
        normalized = self._normalize_text(brand_name)
        
        # Exakte Suche
        for brand_id, brand in self.brands.items():
            if brand['normalized_name'] == normalized:
                return brand_id
        
        # Fuzzy-Suche (z.B. "Danone" vs "DANONE")
        for brand_id, brand in self.brands.items():
            if self._similarity(brand['normalized_name'], normalized) > 0.9:
                logger.debug(f"Marke gefunden via Fuzzy: {brand_name} → {brand['name']}")
                return brand_id
        
        # Neue Marke erstellen
        brand_id = f"brand_{len(self.brands) + 1:04d}"
        self.brands[brand_id] = {
            "id": brand_id,
            "name": brand_name.strip(),
            "normalized_name": normalized,
            "product_count": 0
        }
        logger.info(f"Neue Marke erstellt: {brand_name} ({brand_id})")
        return brand_id
    
    def find_similar_product(self, name, brand_id, category, threshold=0.85):
        """
        Sucht nach ähnlichem Produkt in der Datenbank.
        Berücksichtigt Name, Marke und Kategorie.
        """
        normalized_name = self._normalize_text(name)
        
        best_match = None
        best_score = 0
        
        for prod_id, prod in self.products.items():
            # Muss gleiche Marke und Kategorie haben
            if prod['brand_id'] != brand_id or prod['category'] != category:
                continue
            
            # Name-Ähnlichkeit
            similarity = self._similarity(prod['normalized_name'], normalized_name)
            
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = prod_id
        
        if best_match:
            logger.debug(f"Ähnliches Produkt gefunden: {name} → {self.products[best_match]['name']} (Score: {best_score:.2f})")
        
        return best_match
    
    def add_or_update_product(self, offer_data):
        """
        Fügt Angebot zur Datenbank hinzu oder updated existierendes Produkt.
        
        Args:
            offer_data: Dict mit keys: title, brand, category, price, unit_price, 
                       base_unit, amount, store_slug, valid_until
        
        Returns:
            product_id des gespeicherten Produkts
        """
        # Marke verarbeiten
        brand_id = self.get_or_create_brand(offer_data.get('brand', ''))
        
        # Produkt suchen oder erstellen
        product_id = self.find_similar_product(
            offer_data['title'],
            brand_id,
            offer_data['category']
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        if product_id:
            # Update existierendes Produkt
            product = self.products[product_id]
            product['last_seen'] = today
            product['total_observations'] += 1
            
            if offer_data['store_slug'] not in product['stores_available']:
                product['stores_available'].append(offer_data['store_slug'])
        else:
            # Neues Produkt erstellen
            product_id = self._generate_product_id(offer_data['title'], offer_data.get('brand', ''))
            
            self.products[product_id] = {
                "id": product_id,
                "name": offer_data['title'],
                "brand_id": brand_id,
                "normalized_name": self._normalize_text(offer_data['title']),
                "base_unit": offer_data['base_unit'],
                "standard_amount": offer_data['amount'],
                "category": offer_data['category'],
                "first_seen": today,
                "last_seen": today,
                "stores_available": [offer_data['store_slug']],
                "total_observations": 1
            }
            
            # Brand-Counter erhöhen
            if brand_id and brand_id in self.brands:
                self.brands[brand_id]['product_count'] += 1
            
            logger.info(f"Neues Produkt erstellt: {offer_data['title']} ({product_id})")
        
        # Preis-Historie hinzufügen
        self._add_price_entry(product_id, offer_data)
        
        return product_id
    
    def _add_price_entry(self, product_id, offer_data):
        """Fügt Preispunkt zur Historie hinzu."""
        if product_id not in self.price_history:
            self.price_history[product_id] = {}
        
        store = offer_data['store_slug']
        if store not in self.price_history[product_id]:
            self.price_history[product_id][store] = []
        
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # ← NEU: Zeitstempel
        
        # Prüfe ob heute schon ein Eintrag existiert
        store_history = self.price_history[product_id][store]
        existing_entry = next((e for e in store_history if e['date'] == today), None)
        
        if existing_entry:
            # Update existierenden Eintrag
            existing_entry['price'] = offer_data['price']
            existing_entry['unit_price'] = offer_data['unit_price']
            existing_entry['valid_until'] = offer_data.get('valid_until', '')
            existing_entry['scanned_at'] = now  # ← NEU
        else:
            # Neuen Eintrag hinzufügen
            store_history.append({
                "date": today,
                "scanned_at": now,  # ← NEU
                "price": offer_data['price'],
                "unit_price": offer_data['unit_price'],
                "valid_until": offer_data.get('valid_until', '')
            })
    
    def get_price_statistics(self, product_id):
        """
        Berechnet Preis-Statistiken für ein Produkt.
        
        Returns:
            Dict mit avg_price, min_price, max_price, price_trend pro Store
        """
        if product_id not in self.price_history:
            return {}
        
        stats = {}
        
        for store, history in self.price_history[product_id].items():
            if not history:
                continue
            
            prices = [entry['price'] for entry in history]
            unit_prices = [entry['unit_price'] for entry in history]
            
            # Letzter Eintrag für Ablaufdatum
            latest_entry = history[-1]
            days_left = self._days_until_expiry(latest_entry.get('valid_until'))
            
            stats[store] = {
                "avg_price": round(sum(prices) / len(prices), 2),
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_unit_price": round(sum(unit_prices) / len(unit_prices), 2),
                "min_unit_price": min(unit_prices),
                "max_unit_price": max(unit_prices),
                "observations": len(history),
                "first_price": history[0]['price'],
                "latest_price": history[-1]['price'],
                "price_change": round(history[-1]['price'] - history[0]['price'], 2) if len(history) > 1 else 0,
                "valid_until": latest_entry.get('valid_until', ''),
                "days_until_expiry": days_left,
                "last_scanned": latest_entry.get('scanned_at', latest_entry['date'])
            }
        
        return stats
    
    def get_product_report(self, product_id):
        """Generiert kompletten Report für ein Produkt."""
        if product_id not in self.products:
            return None
        
        product = self.products[product_id]
        brand = self.brands.get(product['brand_id'], {})
        stats = self.get_price_statistics(product_id)
        
        return {
            "product": product,
            "brand": brand,
            "price_stats": stats
        }
    
    def save_all(self):
        """Speichert alle Datenbanken."""
        logger.info("Speichere Produkt-Datenbanken...")
        self._save_json(self.products_file, self.products)
        self._save_json(self.brands_file, self.brands)
        self._save_json(self.price_history_file, self.price_history)
        logger.info(f"✓ Gespeichert: {len(self.products)} Produkte, {len(self.brands)} Marken")
    
    def get_top_deals(self, limit=10):
        """
        Findet die besten aktuellen Deals basierend auf historischen Preisen.
        
        Returns:
            Liste von Dicts mit Produkt-Info und Ersparnis
        """
        deals = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        for product_id, product in self.products.items():
            if product_id not in self.price_history:
                continue
            
            for store, history in self.price_history[product_id].items():
                if not history:
                    continue
                
                # Letzter Preis (heute)
                latest_entry = history[-1]
                if latest_entry['date'] != today:
                    continue
                
                # Durchschnittspreis berechnen
                prices = [e['unit_price'] for e in history]
                avg_price = sum(prices) / len(prices)
                current_price = latest_entry['unit_price']
                
                # Nur wenn mindestens 10% günstiger als Durchschnitt
                if current_price < avg_price * 0.9:
                    savings_percent = round(((avg_price - current_price) / avg_price) * 100, 1)
                    
                    brand = self.brands.get(product['brand_id'], {})
                    days_left = self._days_until_expiry(latest_entry.get('valid_until'))
                    
                    deals.append({
                        "product_id": product_id,
                        "name": product['name'],
                        "brand": brand.get('name', ''),
                        "category": product['category'],
                        "store": store,
                        "current_price": current_price,
                        "avg_price": round(avg_price, 2),
                        "savings_percent": savings_percent,
                        "base_unit": product['base_unit'],
                        "valid_until": latest_entry.get('valid_until', ''),
                        "days_until_expiry": days_left
                    })
        
        # Sortiere nach Ersparnis
        deals.sort(key=lambda x: x['savings_percent'], reverse=True)
        return deals[:limit]
    
    def get_expiring_soon(self, days=3, limit=20):
        """
        Findet Angebote die in X Tagen ablaufen.
        
        Args:
            days: Anzahl Tage bis Ablauf
            limit: Max Anzahl Ergebnisse
        
        Returns:
            Liste von Dicts mit Produkt-Info
        """
        expiring = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        for product_id, product in self.products.items():
            if product_id not in self.price_history:
                continue
            
            for store, history in self.price_history[product_id].items():
                if not history:
                    continue
                
                latest_entry = history[-1]
                if latest_entry['date'] != today:
                    continue
                
                days_left = self._days_until_expiry(latest_entry.get('valid_until'))
                
                if days_left is not None and 0 <= days_left <= days:
                    brand = self.brands.get(product['brand_id'], {})
                    
                    expiring.append({
                        "product_id": product_id,
                        "name": product['name'],
                        "brand": brand.get('name', ''),
                        "category": product['category'],
                        "store": store,
                        "price": latest_entry['price'],
                        "unit_price": latest_entry['unit_price'],
                        "base_unit": product['base_unit'],
                        "valid_until": latest_entry.get('valid_until', ''),
                        "days_until_expiry": days_left
                    })
        
        # Sortiere nach Ablaufdatum (dringendste zuerst)
        expiring.sort(key=lambda x: x['days_until_expiry'])
        return expiring[:limit]
