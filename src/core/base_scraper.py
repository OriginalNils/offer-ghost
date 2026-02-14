from abc import ABC, abstractmethod

class BaseScraper(ABC):
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        print(f"   [INIT] {self.__class__.__name__} geladen.")

    @abstractmethod
    def fetch_data(self):
        pass

    @abstractmethod
    def parse_data(self, raw_data):
        pass

    def run(self):
        print(f"   [RUN] === {self.__class__.__name__} gestartet ===")
        raw = self.fetch_data()
        
        if raw:
            print(f"   [RUN] Daten empfangen, starte Parsing...")
            results = self.parse_data(raw)
            print(f"   [RUN] Fertig! {len(results)} Angebote gefunden.")
            return results
        
        print(f"   [RUN] Abbruch: Keine Daten erhalten.")
        return []