import json
from openai import OpenAI
from src.config import OPENROUTER_API_KEY, AI_MODEL

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def extract_units_with_ai(items_data):
    """
    Extrahiert Mengen aus Beschreibungen mit einem präzisen Prompt und Fehlerbehandlung.
    """
    if not items_data:
        return {}

    # Der System-Prompt setzt die Regeln fest
    system_instruction = """Du bist ein präziser Daten-Extraktor. Deine Aufgabe ist es, aus Supermarkt-Beschreibungen die Gesamtmenge zu berechnen und die Einheit zu normalisieren.

VERHALTENSREGELN:
1. Berechne die Gesamtmenge (Menge x Volumen/Gewicht). 
   Beispiel: '8 x 100g' -> amount: 0.8, unit: 'kg'
2. Einheiten-Konvertierung: 
   - Gramm (g) zu Kilogramm (kg) -> Wert / 1000
   - Milliliter (ml) zu Liter (l) -> Wert / 1000
   - Stück, Becher, Flaschen ohne Volumenangabe -> unit: 'stk'
3. Wenn keine Menge erkennbar ist, nutze amount: 1.0 und unit: 'stk'.
4. Gib AUSSCHLIESSLICH ein valides JSON-Objekt zurück. Kein Text davor oder danach.

FORMATBEISPIEL:
{
  "results": [
    {"id": 0, "amount": 0.5, "unit": "kg"},
    {"id": 1, "amount": 0.75, "unit": "l"}
  ]
}"""

    # Der User-Prompt enthält die eigentlichen Daten
    user_prompt = f"Verarbeite diese Datenliste und gib nur das JSON zurück:\n{json.dumps(items_data)}"

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            # Wir erzwingen das JSON-Format, falls das Modell es unterstützt
            response_format={"type": "json_object"},
            temperature=0.1 # Niedrige Temperatur für weniger "Kreativität" und mehr Präzision
        )
        
        content = response.choices[0].message.content
        
        # Sicherheits-Check: Falls die KI doch Markdown-Code-Blocks (```json) mitschickt
        clean_content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(clean_content)
        results = data.get("results", [])
        
        # Umwandlung in ein Dictionary für schnellen Zugriff im Scraper
        return {item['id']: item for item in results if 'id' in item}

    except Exception as e:
        print(f"      [AI-ERROR] Fehler bei der KI-Extraktion: {e}")
        # Fallback: Für jedes Item Standardwerte zurückgeben, damit der Scraper nicht crasht
        return {item['id']: {"amount": 1.0, "unit": "stk"} for item in items_data}