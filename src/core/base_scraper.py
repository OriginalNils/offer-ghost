import logging
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.logger.info(f"Scraper initialisiert")

    @abstractmethod
    def fetch_data(self):
        """Holt Rohdaten von der API/Website."""
        pass

    @abstractmethod
    def parse_data(self, raw_data):
        """Verarbeitet Rohdaten zu strukturierten Angeboten."""
        pass

    def run(self):
        """Führt den kompletten Scraping-Prozess aus."""
        self.logger.info("=== Scraping-Prozess gestartet ===")
        raw = self.fetch_data()
        
        if raw:
            self.logger.info("Daten empfangen, starte Parsing...")
            results = self.parse_data(raw)
            self.logger.info(f"Fertig! {len(results)} Angebote gefunden.")
            return results
        
        self.logger.warning("Abbruch: Keine Daten erhalten.")
        return []
