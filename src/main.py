import json
import os
from src.config import ZIP_CODE, DATA_DIR, TRACKED_STORES
from src.scrapers.marktguru import MarktguruScraper

def save_to_json(data, store_name):
    filename = f"{store_name}_offers.json"
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"   ✅ {store_name.upper()} gespeichert in: {path}")

def main():
    print(f"--- 👻 Offer-Ghost: Multi-Store Scan (PLZ: {ZIP_CODE}) ---")
    
    total_found = 0
    
    for store_slug in TRACKED_STORES:
        # Scraper für den jeweiligen Markt erstellen
        scraper = MarktguruScraper(zip_code=ZIP_CODE, retailer_slug=store_slug)
        
        # Ausführen
        results = scraper.run()
        
        if results:
            save_to_json(results, store_slug)
            total_found += len(results)
        else:
            print(f"   ⚠️ Keine Angebote für {store_slug.upper()} gefunden.")

    print(f"\n--- 👻 Scan beendet. Insgesamt {total_found} Angebote gefunden. ---")

if __name__ == "__main__":
    main()