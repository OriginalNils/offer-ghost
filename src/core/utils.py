import re

def normalize_price(description, price):
    """
    Versucht Gewicht/Volumen aus der Beschreibung zu extrahieren 
    und berechnet den Preis pro kg/L.
    """
    if not description or not price:
        return None, None

    # Suche nach Mustern wie "500g", "0,75-l", "1kg", "8 x 100g"
    # Regex erklärt: (Zahl) (optionales x Zahl) (Einheit)
    pattern = r"(\d+(?:,\d+)?)\s*(?:x\s*(\d+(?:,\d+)?))?\s*(g|kg|l|ml|stk|fl)"
    match = re.search(pattern, description.lower().replace(",", "."))

    if not match:
        return None, None

    val1 = float(match.group(1))
    val2 = float(match.group(2)) if match.group(2) else 1.0
    unit = match.group(3)

    total_qty = val1 * val2
    base_unit = ""
    unit_price = 0.0

    # Normalisierung auf kg oder Liter
    if unit in ["g", "ml"]:
        unit_price = (price / total_qty) * 1000
        base_unit = "kg" if unit == "g" else "l"
    elif unit in ["kg", "l"]:
        unit_price = price / total_qty
        base_unit = unit
    else:
        unit_price = price / total_qty
        base_unit = unit # z.B. Stück

    return round(unit_price, 2), base_unit