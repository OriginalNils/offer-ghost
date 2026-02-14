import time
from functools import wraps


def normalize_price(price_str):
    """Konvertiert verschiedene Preis-Formate zu float."""
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    if isinstance(price_str, str):
        price_str = price_str.replace(',', '.').replace('€', '').strip()
        try:
            return float(price_str)
        except ValueError:
            return 0.0
    
    return 0.0


def calculate_unit_price(price, amount, unit):
    """Berechnet Grundpreis mit Fehlerbehandlung."""
    if not amount or amount <= 0:
        return price
    return round(price / amount, 2)


def clean_product_name(name):
    """Entfernt überflüssige Zeichen und mehrfache Leerzeichen aus Produktnamen."""
    if not name:
        return "Unbekannt"
    return ' '.join(name.split())


def rate_limit(calls_per_second=2):
    """Decorator für Rate Limiting von API-Calls."""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator
