"""
CLI-Tool zum Inspizieren der Produkt-Datenbank.

Usage:
  python -m src.tools.product_inspector search "Milch"
  python -m src.tools.product_inspector product prod_abc123
  python -m src.tools.product_inspector brand brand_001
  python -m src.tools.product_inspector stats
  python -m src.tools.product_inspector expiring 3
"""

import sys
import json
from src.config import DATA_DIR
from src.core.product_tracker import ProductTracker


def search_products(tracker, query):
    """Sucht Produkte nach Name."""
    query_lower = query.lower()
    results = []
    
    for prod_id, prod in tracker.products.items():
        if query_lower in prod['normalized_name']:
            results.append((prod_id, prod))
    
    print(f"\n🔍 Gefunden: {len(results)} Produkte für '{query}'\n")
    
    for prod_id, prod in results[:20]:  # Max 20
        brand = tracker.brands.get(prod['brand_id'], {})
        print(f"  [{prod_id}] {prod['name']}")
        print(f"    Marke: {brand.get('name', 'Unbekannt')}")
        print(f"    Kategorie: {prod['category']}")
        print(f"    Stores: {', '.join(prod['stores_available'])}")
        print(f"    Beobachtungen: {prod['total_observations']}")
        print()


def show_product(tracker, product_id):
    """Zeigt detaillierte Produkt-Info."""
    report = tracker.get_product_report(product_id)
    
    if not report:
        print(f"❌ Produkt {product_id} nicht gefunden.")
        return
    
    prod = report['product']
    brand = report['brand']
    stats = report['price_stats']
    
    print("\n" + "="*70)
    print(f"  PRODUKT: {prod['name']}")
    print("="*70)
    print(f"Marke: {brand.get('name', 'Unbekannt')}")
    print(f"Kategorie: {prod['category']}")
    print(f"Einheit: {prod['standard_amount']} {prod['base_unit']}")
    print(f"Erstmals gesehen: {prod['first_seen']}")
    print(f"Zuletzt gesehen: {prod['last_seen']}")
    print(f"Verfügbar bei: {', '.join(prod['stores_available'])}")
    print(f"Gesamt-Beobachtungen: {prod['total_observations']}")
    
    print("\n📊 PREIS-STATISTIKEN:\n")
    
    for store, stat in stats.items():
        print(f"  {store.upper()}:")
        print(f"    Durchschnitt: {stat['avg_price']:.2f}€ ({stat['avg_unit_price']:.2f}€/{prod['base_unit']})")
        print(f"    Min/Max: {stat['min_price']:.2f}€ / {stat['max_price']:.2f}€")
        print(f"    Trend: {stat['price_change']:+.2f}€ ({stat['observations']} Messungen)")
        
        # NEU: Ablaufdatum anzeigen
        if stat.get('valid_until'):
            valid_until_raw = stat['valid_until']
            
            # Formatiere Datum schöner
            if 'T' in valid_until_raw:
                valid_until_date = valid_until_raw.split('T')[0]
                valid_until_time = valid_until_raw.split('T')[1].replace('Z', ' UTC')
                expiry_info = f"{valid_until_date} {valid_until_time}"
            else:
                expiry_info = valid_until_raw
            
            days_left = stat.get('days_until_expiry')
            
            if days_left is not None:
                if days_left == 0:
                    expiry_info += " ⚠️ LÄUFT HEUTE AB"
                elif days_left == 1:
                    expiry_info += " ⚠️ Läuft morgen ab"
                elif days_left <= 3:
                    expiry_info += f" ⚠️ Noch {days_left} Tage"
                else:
                    expiry_info += f" (noch {days_left} Tage)"
            
            print(f"    Gültig bis: {expiry_info}")
        
        # NEU: Letzter Scan
        if stat.get('last_scanned'):
            print(f"    Letzter Scan: {stat['last_scanned']}")
        
        print()



def show_brand(tracker, brand_id):
    """Zeigt Marken-Info."""
    if brand_id not in tracker.brands:
        print(f"❌ Marke {brand_id} nicht gefunden.")
        return
    
    brand = tracker.brands[brand_id]
    
    print("\n" + "="*60)
    print(f"  MARKE: {brand['name']}")
    print("="*60)
    print(f"ID: {brand['id']}")
    print(f"Produkte: {brand['product_count']}")
    
    # Finde Produkte dieser Marke
    products = [p for p in tracker.products.values() if p['brand_id'] == brand_id]
    
    print(f"\nProdukte ({len(products)}):")
    for prod in products[:20]:
        print(f"  - {prod['name']} ({prod['category']})")


def show_stats(tracker):
    """Zeigt Gesamt-Statistiken."""
    print("\n" + "="*60)
    print("  📊 DATENBANK-STATISTIKEN")
    print("="*60)
    print(f"Produkte: {len(tracker.products)}")
    print(f"Marken: {len(tracker.brands)}")
    
    # Kategorie-Verteilung
    categories = {}
    for prod in tracker.products.values():
        cat = prod['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nProdukte nach Kategorien:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:<25}: {count:>3}")
    
    # Top Marken
    print("\nTop 10 Marken:")
    valid_brands = [b for b in tracker.brands.values() if b.get('product_count', 0) > 0]
    top_brands = sorted(valid_brands, key=lambda x: x['product_count'], reverse=True)[:10]
    for brand in top_brands:
        print(f"  {brand['name']:<20}: {brand['product_count']:>3} Produkte")


def show_expiring(tracker, days):
    """Zeigt Angebote die bald ablaufen."""
    expiring = tracker.get_expiring_soon(days=int(days))
    
    if not expiring:
        print(f"\n✅ Keine Angebote laufen in den nächsten {days} Tagen ab.\n")
        return
    
    # NEU: Klarere Beschreibung
    if days == 0:
        title = "⏰ ANGEBOTE DIE HEUTE ABLAUFEN"
    elif days == 1:
        title = "⏰ ANGEBOTE DIE BIS MORGEN ABLAUFEN"
    else:
        title = f"⏰ ANGEBOTE DIE IN DEN NÄCHSTEN {days} TAGEN ABLAUFEN"
    
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)
    print(f"\n{'Produkt':<30} | {'Store':<8} | {'Preis':<12} | {'Läuft ab'}")
    print("-" * 70)
    
    for item in expiring:
        name = item['name'][:28]
        store = item['store'][:8].upper()
        price = f"{item['price']:.2f}€"
        
        days_left = item['days_until_expiry']
        
        # Formatiere Datum schöner (nur YYYY-MM-DD)
        valid_until_raw = item['valid_until']
        if 'T' in valid_until_raw:
            valid_until_date = valid_until_raw.split('T')[0]
        else:
            valid_until_date = valid_until_raw
        
        if days_left == 0:
            expiry = f"{valid_until_date} ⚠️ HEUTE"
        elif days_left == 1:
            expiry = f"{valid_until_date} ⚠️ MORGEN"
        else:
            expiry = f"{valid_until_date} (in {days_left}d)"
        
        print(f"{name:<30} | {store:<8} | {price:<12} | {expiry}")
    
    print("="*70 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.tools.product_inspector search 'Milch'")
        print("  python -m src.tools.product_inspector product prod_abc123")
        print("  python -m src.tools.product_inspector brand brand_001")
        print("  python -m src.tools.product_inspector stats")
        print("  python -m src.tools.product_inspector expiring 3")
        return
    
    tracker = ProductTracker(DATA_DIR)
    command = sys.argv[1]
    
    if command == "search" and len(sys.argv) > 2:
        search_products(tracker, sys.argv[2])
    elif command == "product" and len(sys.argv) > 2:
        show_product(tracker, sys.argv[2])
    elif command == "brand" and len(sys.argv) > 2:
        show_brand(tracker, sys.argv[2])
    elif command == "stats":
        show_stats(tracker)
    elif command == "expiring" and len(sys.argv) > 2:
        show_expiring(tracker, sys.argv[2])
    else:
        print("❌ Unbekannter Befehl oder fehlende Parameter")


if __name__ == "__main__":
    main()
