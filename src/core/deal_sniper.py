import json
import os
import logging
from datetime import datetime
from src.config import DATA_DIR

logger = logging.getLogger(__name__)


class DealSniper:
    """
    Deal-Sniper: Automatische Deal-Erkennung basierend auf Regeln.
    """
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.sniper_dir = os.path.join(data_dir, "sniper")
        
        # Pfade
        self.rules_file = os.path.join(self.sniper_dir, "rules.json")
        self.alerts_file = os.path.join(self.sniper_dir, "alerts.json")
        
        # Verzeichnis erstellen
        os.makedirs(self.sniper_dir, exist_ok=True)
        
        # Daten laden
        self.rules = self._load_json(self.rules_file, self._default_rules())
        self.alerts = self._load_json(self.alerts_file, [])
        
        logger.info(f"Deal-Sniper initialisiert: {len(self.rules)} Regeln")
    
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
    
    def _default_rules(self):
        """Erstellt Standard-Regeln."""
        return {
            "price_alerts": [],
            "category_alerts": [],
            "brand_alerts": [],
            "percentage_threshold": 20,  # Min 20% Rabatt
            "new_all_time_low": True
        }
    
    def add_price_alert(self, product_name_pattern, max_price, store=None):
        """
        Fügt Preis-Alert hinzu.
        
        Args:
            product_name_pattern: Name oder Teilname des Produkts (z.B. "Milch")
            max_price: Maximaler Preis (alert wenn darunter)
            store: Optional - nur bestimmter Store
        """
        alert = {
            "id": len(self.rules["price_alerts"]) + 1,
            "pattern": product_name_pattern.lower(),
            "max_price": max_price,
            "store": store,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": True
        }
        
        self.rules["price_alerts"].append(alert)
        self._save_json(self.rules_file, self.rules)
        
        logger.info(f"Preis-Alert erstellt: '{product_name_pattern}' unter {max_price}€")
        return alert["id"]
    
    def add_category_alert(self, category, max_unit_price, unit="kg"):
        """
        Fügt Kategorie-Alert hinzu.
        
        Args:
            category: Kategorie-Name (z.B. "Fleisch & Fisch")
            max_unit_price: Max Grundpreis (z.B. 10€/kg)
            unit: Einheit (kg, l, stk)
        """
        alert = {
            "id": len(self.rules["category_alerts"]) + 1,
            "category": category,
            "max_unit_price": max_unit_price,
            "unit": unit,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": True
        }
        
        self.rules["category_alerts"].append(alert)
        self._save_json(self.rules_file, self.rules)
        
        logger.info(f"Kategorie-Alert erstellt: '{category}' unter {max_unit_price}€/{unit}")
        return alert["id"]
    
    def add_brand_alert(self, brand_name):
        """
        Fügt Marken-Alert hinzu (alle Produkte dieser Marke).
        
        Args:
            brand_name: Markenname (z.B. "Ferrero")
        """
        alert = {
            "id": len(self.rules["brand_alerts"]) + 1,
            "brand": brand_name.lower(),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": True
        }
        
        self.rules["brand_alerts"].append(alert)
        self._save_json(self.rules_file, self.rules)
        
        logger.info(f"Marken-Alert erstellt: '{brand_name}'")
        return alert["id"]
    
    def remove_alert(self, alert_type, alert_id):
        """
        Entfernt Alert.
        
        Args:
            alert_type: "price", "category", oder "brand"
            alert_id: ID des Alerts
        """
        key = f"{alert_type}_alerts"
        
        if key not in self.rules:
            logger.error(f"Unbekannter Alert-Typ: {alert_type}")
            return False
        
        self.rules[key] = [a for a in self.rules[key] if a["id"] != alert_id]
        self._save_json(self.rules_file, self.rules)
        
        logger.info(f"Alert #{alert_id} entfernt")
        return True
    
    def scan_for_deals(self, tracker):
        """
        Scannt ProductTracker nach Deals basierend auf Regeln.
        
        Args:
            tracker: ProductTracker-Instanz
        
        Returns:
            Liste von gefundenen Deals
        """
        found_deals = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        logger.info("Starte Deal-Sniper Scan...")
        
        # 1. Preis-Alerts prüfen
        for alert in self.rules["price_alerts"]:
            if not alert.get("active", True):
                continue
            
            pattern = alert["pattern"]
            max_price = alert["max_price"]
            store_filter = alert.get("store")
            
            for product_id, product in tracker.products.items():
                # Name-Match
                if pattern not in product["normalized_name"]:
                    continue
                
                # Preis-Historie checken
                if product_id not in tracker.price_history:
                    continue
                
                for store, history in tracker.price_history[product_id].items():
                    if not history:
                        continue
                    
                    # Store-Filter
                    if store_filter and store != store_filter:
                        continue
                    
                    latest = history[-1]
                    if latest["date"] != today:
                        continue
                    
                    # Preis-Check
                    if latest["price"] <= max_price:
                        brand = tracker.brands.get(product["brand_id"], {})
                        
                        deal = {
                            "type": "price_alert",
                            "alert_id": alert["id"],
                            "product_id": product_id,
                            "name": product["name"],
                            "brand": brand.get("name", ""),
                            "category": product["category"],
                            "store": store,
                            "price": latest["price"],
                            "unit_price": latest["unit_price"],
                            "base_unit": product["base_unit"],
                            "target_price": max_price,
                            "valid_until": latest.get("valid_until", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        found_deals.append(deal)
                        logger.info(f"🎯 Preis-Alert: {product['name']} bei {store} für {latest['price']}€")
        
        # 2. Kategorie-Alerts prüfen
        for alert in self.rules["category_alerts"]:
            if not alert.get("active", True):
                continue
            
            category = alert["category"]
            max_unit_price = alert["max_unit_price"]
            unit_filter = alert["unit"]
            
            for product_id, product in tracker.products.items():
                # Kategorie-Match
                if product["category"] != category:
                    continue
                
                # Einheit-Match
                if product["base_unit"] != unit_filter:
                    continue
                
                # Preis-Historie checken
                if product_id not in tracker.price_history:
                    continue
                
                for store, history in tracker.price_history[product_id].items():
                    if not history:
                        continue
                    
                    latest = history[-1]
                    if latest["date"] != today:
                        continue
                    
                    # Grundpreis-Check
                    if latest["unit_price"] <= max_unit_price:
                        brand = tracker.brands.get(product["brand_id"], {})
                        
                        deal = {
                            "type": "category_alert",
                            "alert_id": alert["id"],
                            "product_id": product_id,
                            "name": product["name"],
                            "brand": brand.get("name", ""),
                            "category": product["category"],
                            "store": store,
                            "price": latest["price"],
                            "unit_price": latest["unit_price"],
                            "base_unit": product["base_unit"],
                            "target_unit_price": max_unit_price,
                            "valid_until": latest.get("valid_until", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        found_deals.append(deal)
                        logger.info(f"🎯 Kategorie-Alert: {product['name']} bei {store} für {latest['unit_price']}€/{unit_filter}")
        
        # 3. Marken-Alerts prüfen
        for alert in self.rules["brand_alerts"]:
            if not alert.get("active", True):
                continue
            
            brand_pattern = alert["brand"]
            
            # Finde passende Marken
            matching_brand_ids = []
            for brand_id, brand in tracker.brands.items():
                if brand_pattern in brand["normalized_name"]:
                    matching_brand_ids.append(brand_id)
            
            for product_id, product in tracker.products.items():
                if product["brand_id"] not in matching_brand_ids:
                    continue
                
                # Preis-Historie checken
                if product_id not in tracker.price_history:
                    continue
                
                for store, history in tracker.price_history[product_id].items():
                    if not history:
                        continue
                    
                    latest = history[-1]
                    if latest["date"] != today:
                        continue
                    
                    brand = tracker.brands.get(product["brand_id"], {})
                    
                    deal = {
                        "type": "brand_alert",
                        "alert_id": alert["id"],
                        "product_id": product_id,
                        "name": product["name"],
                        "brand": brand.get("name", ""),
                        "category": product["category"],
                        "store": store,
                        "price": latest["price"],
                        "unit_price": latest["unit_price"],
                        "base_unit": product["base_unit"],
                        "valid_until": latest.get("valid_until", ""),
                        "found_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    found_deals.append(deal)
                    logger.info(f"🎯 Marken-Alert: {product['name']} von {brand.get('name', '')} bei {store}")
        
        # 4. Prozentuale Rabatte (nur wenn genug Historie)
        threshold = self.rules.get("percentage_threshold", 20)
        
        for product_id, product in tracker.products.items():
            if product_id not in tracker.price_history:
                continue
            
            for store, history in tracker.price_history[product_id].items():
                if len(history) < 2:  # Mindestens 2 Einträge für Vergleich
                    continue
                
                latest = history[-1]
                if latest["date"] != today:
                    continue
                
                # Durchschnitt der vorherigen Preise
                prev_prices = [e["unit_price"] for e in history[:-1]]
                avg_prev = sum(prev_prices) / len(prev_prices)
                current = latest["unit_price"]
                
                # Rabatt berechnen
                if avg_prev > 0:
                    discount_percent = ((avg_prev - current) / avg_prev) * 100
                    
                    if discount_percent >= threshold:
                        brand = tracker.brands.get(product["brand_id"], {})
                        
                        deal = {
                            "type": "percentage_discount",
                            "product_id": product_id,
                            "name": product["name"],
                            "brand": brand.get("name", ""),
                            "category": product["category"],
                            "store": store,
                            "price": latest["price"],
                            "unit_price": latest["unit_price"],
                            "base_unit": product["base_unit"],
                            "avg_previous": round(avg_prev, 2),
                            "discount_percent": round(discount_percent, 1),
                            "valid_until": latest.get("valid_until", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        found_deals.append(deal)
                        logger.info(f"🎯 Rabatt-Alert: {product['name']} bei {store} ({discount_percent:.1f}% günstiger)")
        
        # 5. All-Time-Low (historisches Tief)
        if self.rules.get("new_all_time_low", False):
            for product_id, product in tracker.products.items():
                if product_id not in tracker.price_history:
                    continue
                
                for store, history in tracker.price_history[product_id].items():
                    if len(history) < 3:  # Mindestens 3 Einträge
                        continue
                    
                    latest = history[-1]
                    if latest["date"] != today:
                        continue
                    
                    # Ist aktueller Preis der niedrigste?
                    all_prices = [e["unit_price"] for e in history]
                    min_price = min(all_prices)
                    
                    if latest["unit_price"] == min_price and all_prices.count(min_price) == 1:
                        brand = tracker.brands.get(product["brand_id"], {})
                        prev_min = min([p for p in all_prices if p != min_price]) if len(all_prices) > 1 else min_price
                        
                        deal = {
                            "type": "all_time_low",
                            "product_id": product_id,
                            "name": product["name"],
                            "brand": brand.get("name", ""),
                            "category": product["category"],
                            "store": store,
                            "price": latest["price"],
                            "unit_price": latest["unit_price"],
                            "base_unit": product["base_unit"],
                            "previous_low": prev_min,
                            "valid_until": latest.get("valid_until", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        found_deals.append(deal)
                        logger.info(f"🎯 All-Time-Low: {product['name']} bei {store}")
        
        # Deals speichern
        if found_deals:
            self.alerts.extend(found_deals)
            self._save_json(self.alerts_file, self.alerts)
            logger.info(f"✅ {len(found_deals)} neue Deals gefunden")
        
        return found_deals
    
    def get_alerts_today(self):
        """Gibt alle Alerts von heute zurück."""
        today = datetime.now().strftime("%Y-%m-%d")
        return [a for a in self.alerts if a.get("found_at", "").startswith(today)]
    
    def clear_old_alerts(self, days=7):
        """Löscht Alerts älter als X Tage."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        old_count = len(self.alerts)
        self.alerts = [a for a in self.alerts if a.get("found_at", "") >= cutoff]
        
        removed = old_count - len(self.alerts)
        if removed > 0:
            self._save_json(self.alerts_file, self.alerts)
            logger.info(f"🗑️ {removed} alte Alerts gelöscht")
        
        return removed
    
    def save(self):
        """Speichert alle Daten."""
        self._save_json(self.rules_file, self.rules)
        self._save_json(self.alerts_file, self.alerts)
