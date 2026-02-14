"""
CLI-Tool zum Verwalten des Deal-Snipers.

Usage:
  python -m src.tools.sniper_manager add-price "Milch" 1.5
  python -m src.tools.sniper_manager add-category "Fleisch & Fisch" 8.0 kg
  python -m src.tools.sniper_manager add-brand "Ferrero"
  python -m src.tools.sniper_manager list-rules
  python -m src.tools.sniper_manager scan
  python -m src.tools.sniper_manager show-alerts
"""

import sys
from src.config import DATA_DIR
from src.core.deal_sniper import DealSniper
from src.core.product_tracker import ProductTracker


def add_price_alert(sniper, product_pattern, max_price, store=None):
    """Fügt Preis-Alert hinzu."""
    alert_id = sniper.add_price_alert(product_pattern, float(max_price), store)
    print(f"\n✅ Preis-Alert #{alert_id} erstellt:")
    print(f"   Produkt: '{product_pattern}'")
    print(f"   Max-Preis: {max_price}€")
    if store:
        print(f"   Store: {store}")
    print()


def add_category_alert(sniper, category, max_unit_price, unit="kg"):
    """Fügt Kategorie-Alert hinzu."""
    alert_id = sniper.add_category_alert(category, float(max_unit_price), unit)
    print(f"\n✅ Kategorie-Alert #{alert_id} erstellt:")
    print(f"   Kategorie: '{category}'")
    print(f"   Max-Grundpreis: {max_unit_price}€/{unit}")
    print()


def add_brand_alert(sniper, brand_name):
    """Fügt Marken-Alert hinzu."""
    alert_id = sniper.add_brand_alert(brand_name)
    print(f"\n✅ Marken-Alert #{alert_id} erstellt:")
    print(f"   Marke: '{brand_name}'")
    print()


def list_rules(sniper):
    """Zeigt alle Regeln."""
    print("\n" + "="*60)
    print("  🎯 DEAL-SNIPER REGELN")
    print("="*60)
    
    # Preis-Alerts
    price_alerts = sniper.rules.get("price_alerts", [])
    if price_alerts:
        print("\n📍 Preis-Alerts:")
        for alert in price_alerts:
            status = "✅" if alert.get("active", True) else "❌"
            store_info = f" [{alert['store']}]" if alert.get("store") else ""
            print(f"   #{alert['id']}: '{alert['pattern']}' unter {alert['max_price']}€{store_info} {status}")
    
    # Kategorie-Alerts
    cat_alerts = sniper.rules.get("category_alerts", [])
    if cat_alerts:
        print("\n📁 Kategorie-Alerts:")
        for alert in cat_alerts:
            status = "✅" if alert.get("active", True) else "❌"
            print(f"   #{alert['id']}: '{alert['category']}' unter {alert['max_unit_price']}€/{alert['unit']} {status}")
    
    # Marken-Alerts
    brand_alerts = sniper.rules.get("brand_alerts", [])
    if brand_alerts:
        print("\n🏷️ Marken-Alerts:")
        for alert in brand_alerts:
            status = "✅" if alert.get("active", True) else "❌"
            print(f"   #{alert['id']}: '{alert['brand']}' {status}")
    
    # Globale Regeln
    print("\n⚙️ Globale Regeln:")
    print(f"   Rabatt-Schwelle: {sniper.rules.get('percentage_threshold', 20)}%")
    print(f"   All-Time-Low Tracking: {'✅' if sniper.rules.get('new_all_time_low', False) else '❌'}")
    
    print("\n" + "="*60 + "\n")


def scan_deals(sniper):
    """Führt Deal-Scan durch."""
    print("\n🔍 Starte Deal-Sniper Scan...\n")
    
    tracker = ProductTracker(DATA_DIR)
    deals = sniper.scan_for_deals(tracker)
    
    if not deals:
        print("✅ Keine neuen Deals gefunden.\n")
        return
    
    print(f"\n🎯 {len(deals)} Deals gefunden!\n")
    show_deals(deals)


def show_deals(deals):
    """Zeigt gefundene Deals."""
    # Gruppiere nach Typ
    by_type = {}
    for deal in deals:
        deal_type = deal["type"]
        if deal_type not in by_type:
            by_type[deal_type] = []
        by_type[deal_type].append(deal)
    
    for deal_type, type_deals in by_type.items():
        if deal_type == "price_alert":
            print("\n💰 PREIS-ALERTS:")
        elif deal_type == "category_alert":
            print("\n📁 KATEGORIE-DEALS:")
        elif deal_type == "brand_alert":
            print("\n🏷️ MARKEN-DEALS:")
        elif deal_type == "percentage_discount":
            print("\n📉 RABATT-DEALS:")
        elif deal_type == "all_time_low":
            print("\n🏆 HISTORISCHE TIEFSTPREISE:")
        
        print("   " + "-"*60)
        
        for deal in type_deals[:20]:  # Max 20 pro Typ
            name = deal["name"][:35]
            store = deal["store"].upper()
            price = deal["price"]
            unit_price = deal["unit_price"]
            unit = deal["base_unit"]
            
            print(f"\n   {name}")
            print(f"   └─ {store}: {price}€ ({unit_price}€/{unit})")
            
            if deal_type == "price_alert":
                print(f"      Target: {deal['target_price']}€")
            elif deal_type == "category_alert":
                print(f"      Target: {deal['target_unit_price']}€/{unit}")
            elif deal_type == "percentage_discount":
                print(f"      Rabatt: {deal['discount_percent']}% (Ø {deal['avg_previous']}€/{unit})")
            elif deal_type == "all_time_low":
                print(f"      Neues Tief! (vorher: {deal['previous_low']}€/{unit})")


def show_alerts(sniper):
    """Zeigt heutige Alerts."""
    alerts = sniper.get_alerts_today()
    
    if not alerts:
        print("\n✅ Keine Alerts für heute.\n")
        return
    
    print("\n📬 Alerts von heute:")
    show_deals(alerts)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.tools.sniper_manager add-price 'Milch' 1.5")
        print("  python -m src.tools.sniper_manager add-category 'Fleisch & Fisch' 8.0 kg")
        print("  python -m src.tools.sniper_manager add-brand 'Ferrero'")
        print("  python -m src.tools.sniper_manager list-rules")
        print("  python -m src.tools.sniper_manager scan")
        print("  python -m src.tools.sniper_manager show-alerts")
        return
    
    sniper = DealSniper(DATA_DIR)
    command = sys.argv[1]
    
    if command == "add-price" and len(sys.argv) >= 4:
        store = sys.argv[4] if len(sys.argv) > 4 else None
        add_price_alert(sniper, sys.argv[2], sys.argv[3], store)
    elif command == "add-category" and len(sys.argv) >= 4:
        unit = sys.argv[4] if len(sys.argv) > 4 else "kg"
        add_category_alert(sniper, sys.argv[2], sys.argv[3], unit)
    elif command == "add-brand" and len(sys.argv) >= 3:
        add_brand_alert(sniper, sys.argv[2])
    elif command == "list-rules":
        list_rules(sniper)
    elif command == "scan":
        scan_deals(sniper)
    elif command == "show-alerts":
        show_alerts(sniper)
    else:
        print("❌ Unbekannter Befehl oder fehlende Parameter")


if __name__ == "__main__":
    main()
