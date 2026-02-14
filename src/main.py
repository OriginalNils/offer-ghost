import json
import os
import logging
from collections import Counter
from src.config import ZIP_CODE, DATA_DIR, TRACKED_STORES, STORES_CONFIG
from src.scrapers.marktguru import MarktguruScraper
from src.core.product_tracker import ProductTracker
from src.core.deal_sniper import DealSniper


logger = logging.getLogger(__name__)


def save_to_json(data, store_slug):
    """Speichert die Ergebnisse eines Marktes."""
    filename = f"{store_slug}_offers.json"
    path = os.path.join(DATA_DIR, filename)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    logger.info(f"Gespeichert: {filename} ({len(data)} Angebote)")
    return path


def print_summary(all_results):
    """Erstellt eine Statistik nach Kategorien und zeigt Highlights."""
    if not all_results:
        logger.warning("Keine Ergebnisse für Zusammenfassung")
        return

    print("\n" + "="*60)
    print("         📊 GHOST-ZUSAMMENFASSUNG DER WOCHE")
    print("="*60)

    # 1. Gesamtstatistik
    total_offers = len(all_results)
    stores_count = len(set(item['store'] for item in all_results))
    print(f"\n📦 Gesamt: {total_offers} Angebote aus {stores_count} Märkten")

    # 2. Statistik nach Kategorien
    categories = [item.get('category', 'Sonstiges') for item in all_results]
    stats = Counter(categories)

    print("\n🛒 Angebote nach Kategorien:")
    for cat, count in stats.most_common():
        print(f"   - {cat:<25}: {count:>3} Deals")

    # 3. Preis-Highlights (Top 5 beste Grundpreise)
    print("\n🔥 Top-Highlights (Beste Grundpreise):")
    print(f"   {'Produkt':<30} | {'Laden':<12} | {'Preis'}")
    print("   " + "-" * 65)
    
    # Sortiere nach unit_price, filtere unrealistische Werte
    valid_offers = [o for o in all_results if o.get('unit_price', 0) > 0]
    highlights = sorted(valid_offers, key=lambda x: x.get('unit_price', 999))[:5]
    
    for h in highlights:
        title = h['title'][:28]
        store = h['store'][:12]
        price_info = f"{h['price']:.2f}€ ({h['unit_price']:.2f}€/{h['base_unit']})"
        print(f"   {title:<30} | {store:<12} | {price_info}")

    print("\n" + "="*60 + "\n")


def print_top_deals(tracker, limit=10):
    """Zeigt die besten aktuellen Deals basierend auf Preisverlauf."""
    deals = tracker.get_top_deals(limit=limit)
    
    if not deals:
        print("\n⚠️ Keine historischen Deals gefunden (erste Ausführung?)\n")
        return
    
    print("\n" + "="*80)
    print("         💰 TOP-DEALS (basierend auf Preisverlauf)")
    print("="*80)
    print(f"\n{'Produkt':<28} | {'Marke':<10} | {'Store':<6} | {'Ersparnis':<14} | {'Läuft ab'}")
    print("-" * 80)
    
    for deal in deals:
        name = deal['name'][:26]
        brand = deal['brand'][:10]
        store = deal['store'][:6].upper()
        savings = f"-{deal['savings_percent']}%"
        current = f"{deal['current_price']:.2f}€/{deal['base_unit']}"
        avg = f"Ø {deal['avg_price']:.2f}€"
        
        # Ablaufdatum
        days_left = deal.get('days_until_expiry')
        if days_left is not None:
            if days_left == 0:
                expiry = "HEUTE ⚠️"
            elif days_left == 1:
                expiry = "MORGEN ⚠️"
            elif days_left <= 3:
                expiry = f"{days_left}d ⚠️"
            else:
                expiry = f"{days_left}d"
        else:
            expiry = deal.get('valid_until', 'N/A')[:10]
        
        print(f"{name:<28} | {brand:<10} | {store:<6} | {savings:>6} ({current} vs {avg}) | {expiry}")
    
    print("="*80 + "\n")



def main():
    """Hauptfunktion: Orchestriert den gesamten Scraping-Prozess."""
    print(f"\n{'='*60}")
    print(f"   👻 OFFER-GHOST: Multi-Store Scan mit Preis-Tracking")
    print(f"   PLZ: {ZIP_CODE} | Stores: {len(TRACKED_STORES)}")
    print(f"{'='*60}\n")
    
    logger.info(f"Starte Scan für {len(TRACKED_STORES)} Märkte")
    
    # Product Tracker initialisieren
    tracker = ProductTracker(DATA_DIR)
    
    all_offers_collected = []
    
    for store_slug in TRACKED_STORES:
        store_name = STORES_CONFIG['stores'][store_slug]['name']
        print(f"\n🏪 Scanne {store_name}...")
        
        try:
            scraper = MarktguruScraper(zip_code=ZIP_CODE, retailer_slug=store_slug)
            results = scraper.run()
            
            if results:
                save_to_json(results, store_slug)
                all_offers_collected.extend(results)
                
                # Produkte zum Tracker hinzufügen
                logger.info(f"Füge {len(results)} Produkte zum Tracker hinzu...")
                for offer in results:
                    tracker.add_or_update_product(offer)
                
            else:
                logger.warning(f"Keine Angebote für {store_name} gefunden")
                
        except Exception as e:
            logger.error(f"Fehler beim Scrapen von {store_name}: {e}")
            continue

    # Product Tracker speichern
    tracker.save_all()

    # NEU: Deal-Sniper ausführen
    print("\n🎯 Starte Deal-Sniper...\n")
    sniper = DealSniper(DATA_DIR)
    deals = sniper.scan_for_deals(tracker)
    
    if deals:
        print(f"\n🔔 {len(deals)} Deals gefunden!")
        # Zeige Top 5
        for deal in deals[:5]:
            print(f"   • {deal['name']} ({deal['store'].upper()}): {deal['price']}€")
        print(f"\n   Alle Deals: python -m src.tools.sniper_manager show-alerts\n")

    # Zusammenfassung und Master-File
    if all_offers_collected:
        print_summary(all_offers_collected)
        
        # Top Deals basierend auf Preisverlauf
        print_top_deals(tracker, limit=10)
        
        master_path = os.path.join(DATA_DIR, "all_offers_master.json")
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(all_offers_collected, f, indent=4, ensure_ascii=False)
        
        logger.info(f"✅ Scan beendet. {len(all_offers_collected)} Angebote gespeichert")
        print(f"💾 Master-Datenbank: {master_path}")
        print(f"📊 Produkt-DB: {len(tracker.products)} Produkte, {len(tracker.brands)} Marken\n")
    else:
        logger.warning("⚠️ Keine Angebote gefunden!")


if __name__ == "__main__":
    main()
