import json
import hashlib
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Debug-Logging für Imports
logger.debug("=== AI_PROCESSOR: Import-Phase gestartet ===")

try:
    from src.config import OPENROUTER_API_KEY, AI_MODEL, AI_BATCH_SIZE, CACHE_DIR
    logger.debug(f"✓ OPENROUTER_API_KEY: {'SET' if OPENROUTER_API_KEY else 'MISSING'}")
    logger.debug(f"✓ AI_MODEL: {AI_MODEL}")
    logger.debug(f"✓ AI_BATCH_SIZE: {AI_BATCH_SIZE}")
    logger.debug(f"✓ CACHE_DIR: {CACHE_DIR}")
except ImportError as e:
    logger.error(f"✗ Import-Fehler in ai_processor.py: {e}")
    raise

logger.debug("=== AI_PROCESSOR: OpenAI Client wird initialisiert ===")

try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    logger.debug("✓ OpenAI Client erfolgreich erstellt")
except Exception as e:
    logger.error(f"✗ OpenAI Client-Fehler: {e}")
    raise


def extract_units_with_ai(items_data):
    """
    Extrahiert Mengen aus Beschreibungen mit AI und nutzt Caching.
    Verarbeitet Items in Batches für bessere Performance.
    """
    logger.debug(f"=== extract_units_with_ai() aufgerufen mit {len(items_data) if items_data else 0} Items ===")
    
    if not items_data:
        logger.warning("Keine Items zum Verarbeiten erhalten")
        return {}

    # Cache-Key aus Daten generieren
    logger.debug("Generiere Cache-Key...")
    cache_key = hashlib.md5(
        json.dumps(items_data, sort_keys=True).encode()
    ).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    logger.debug(f"Cache-Key: {cache_key}")
    logger.debug(f"Cache-Datei: {cache_file}")
    
    # Aus Cache lesen
    if os.path.exists(cache_file):
        logger.info(f"✓ Cache-Hit! Lade aus {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                logger.debug(f"Cache enthält {len(cached_data)} Einträge")
                return cached_data
        except Exception as e:
            logger.warning(f"Cache-Lesefehler: {e}, führe neuen AI-Call durch")
    else:
        logger.info(f"✗ Cache-Miss. Datei existiert nicht: {cache_file}")
    
    # Verarbeite in Batches
    all_results = {}
    total_items = len(items_data)
    
    logger.info(f"Starte Batch-Verarbeitung: {total_items} Items, Batch-Größe: {AI_BATCH_SIZE}")
    
    for i in range(0, total_items, AI_BATCH_SIZE):
        batch = items_data[i:i+AI_BATCH_SIZE]
        batch_num = (i // AI_BATCH_SIZE) + 1
        total_batches = (total_items + AI_BATCH_SIZE - 1) // AI_BATCH_SIZE
        
        logger.info(f">>> Batch {batch_num}/{total_batches}: Items {i} bis {i+len(batch)-1}")
        logger.debug(f"Batch-Inhalt (erste 2 Items): {json.dumps(batch[:2], ensure_ascii=False)}")
        
        try:
            batch_results = _process_batch(batch, batch_num, total_batches)
            logger.debug(f"Batch {batch_num} Ergebnisse: {len(batch_results)} Items verarbeitet")
            all_results.update(batch_results)
        except Exception as e:
            logger.error(f"✗ Fehler in Batch {batch_num}: {e}", exc_info=True)
            # Fallback für diesen Batch
            for item in batch:
                all_results[item['id']] = {
                    "amount": 1.0,
                    "unit": "stk",
                    "category": "Sonstiges"
                }
    
    logger.info(f"Batch-Verarbeitung abgeschlossen: {len(all_results)} Gesamt-Ergebnisse")
    
    # In Cache schreiben
    try:
        logger.debug(f"Schreibe Ergebnisse in Cache: {cache_file}")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Cache gespeichert: {len(all_results)} Einträge")
    except Exception as e:
        logger.warning(f"✗ Cache-Schreibfehler: {e}")
    
    return all_results


def _process_batch(batch, batch_num=0, total_batches=0):
    """Verarbeitet einen einzelnen Batch mit der AI."""
    logger.debug(f"=== _process_batch() aufgerufen (Batch {batch_num}/{total_batches}) ===")
    logger.debug(f"Batch-Größe: {len(batch)}")
    
    # Prüfe ob AI_MODEL verfügbar ist
    try:
        logger.debug(f"AI_MODEL im Scope: {AI_MODEL}")
    except NameError as e:
        logger.error(f"✗✗✗ KRITISCH: AI_MODEL nicht im Scope! {e}")
        logger.error(f"Verfügbare Globals: {list(globals().keys())}")
        raise
    
    system_instruction = """Du bist ein präziser Daten-Extraktor für deutsche Supermarkt-Angebote.

AUFGABEN:
1. Extrahiere Menge und Einheit aus der Beschreibung
2. Konvertiere in Standard-Einheiten (g→kg, ml→l)
3. Ordne passende Kategorie zu

KATEGORIEN (wähle GENAU eine):
- Obst & Gemüse (z.B. Äpfel, Tomaten, Sellerie, Limetten)
- Fleisch & Fisch (z.B. Hackfleisch, Lachs, Hähnchen, Wurst)
- Milchprodukte & Eier (z.B. Käse, Joghurt, Butter, Milch, Quark)
- Getränke (z.B. Wasser, Saft, Bier, Wein, Kaffee als Getränk)
- Süßes & Snacks (z.B. Schokolade, Chips, Kekse, Gummibärchen)
- Brot & Backwaren (z.B. Brot, Brötchen, Croissants)
- Tiefkühl (z.B. Pizza TK, Gemüse TK, Eis)
- Konserven & Vorrat (z.B. Nudeln, Reis, Konserven, Kaffee/Tee trocken, Mehl, Gewürze)
- Haushalt & Drogerie (z.B. Waschmittel, Shampoo, Putzmittel, Slipeinlagen)
- Sonstiges (nur wenn nichts passt)

WICHTIG:
- Kaffee als Pulver/Granulat → "Konserven & Vorrat"
- Kaffee als fertiges Getränk → "Getränke"
- Elektronik, Werkzeug, Kleidung → "Sonstiges"

KONVERTIERUNGS-REGELN:
- "500g" → amount: 0.5, unit: "kg"
- "1,5l" oder "1.5l" → amount: 1.5, unit: "l"
- "6 x 330ml" → amount: 1.98, unit: "l" (6 × 0.33)
- "1kg" → amount: 1.0, unit: "kg"
- "Stück" oder keine Angabe → amount: 1.0, unit: "stk"

AUSGABEFORMAT (NUR JSON, keine Erklärungen):
{
  "results": [
    {"id": 0, "amount": 0.5, "unit": "kg", "category": "Obst & Gemüse"}
  ]
}"""


    user_prompt = f"Verarbeite diese Datenliste und gib nur das JSON zurück:\n{json.dumps(batch, ensure_ascii=False)}"
    
    logger.debug(f"System-Prompt Länge: {len(system_instruction)} Zeichen")
    logger.debug(f"User-Prompt Länge: {len(user_prompt)} Zeichen")

    try:
        logger.info(f"🤖 Sende Request an OpenRouter (Modell: {AI_MODEL})...")
        
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        logger.debug(f"✓ Response erhalten von OpenRouter")
        logger.debug(f"Response-Typ: {type(response)}")
        
        content = response.choices[0].message.content
        logger.debug(f"Response-Content Länge: {len(content)} Zeichen")
        logger.debug(f"Response-Content Preview: {content[:200]}...")
        
        # Sicherheits-Check: Falls die KI doch Markdown-Code-Blocks mitschickt
        clean_content = content.replace("```json", "").replace("```", "").strip()
        
        if clean_content != content:
            logger.debug("⚠ Markdown-Blöcke wurden entfernt")
        
        logger.debug("Parse JSON...")
        data = json.loads(clean_content)
        results = data.get("results", [])
        
        logger.info(f"✓ AI-Parsing erfolgreich: {len(results)} Ergebnisse")
        logger.debug(f"Erste 2 Ergebnisse: {json.dumps(results[:2], ensure_ascii=False)}")
        
        # Umwandlung in Dictionary für schnellen Zugriff
        result_dict = {item['id']: item for item in results if 'id' in item}
        logger.debug(f"Result-Dict erstellt mit {len(result_dict)} Einträgen")
        
        return result_dict

    except json.JSONDecodeError as e:
        logger.error(f"✗ JSON-Parse-Fehler: {e}")
        logger.error(f"Problematischer Content: {clean_content[:500]}")
        raise
    except Exception as e:
        logger.error(f"✗ AI-Fehler beim Batch-Processing: {e}", exc_info=True)
        logger.error(f"Exception-Typ: {type(e).__name__}")
        
        # Fallback: Standardwerte für alle Items im Batch
        fallback_dict = {
            item['id']: {
                "amount": 1.0, 
                "unit": "stk", 
                "category": "Sonstiges"
            } 
            for item in batch
        }
        logger.warning(f"Verwende Fallback-Werte für {len(fallback_dict)} Items")
        return fallback_dict


logger.debug("=== AI_PROCESSOR: Modul vollständig geladen ===")
