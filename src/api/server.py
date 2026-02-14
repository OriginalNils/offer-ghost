from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from src.core.favorites import FavoritesManager
import os
import logging
from datetime import datetime

from src.config import DATA_DIR, ZIP_CODE, TRACKED_STORES
from src.core.product_tracker import ProductTracker
from src.core.deal_sniper import DealSniper
from src.scrapers.marktguru import MarktguruScraper
from src.core.email_service import EmailService


app = Flask(__name__, 
            template_folder='../../templates',
            static_folder='../../static')
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
tracker = ProductTracker(DATA_DIR)
sniper = DealSniper(DATA_DIR)
favorites = FavoritesManager(DATA_DIR)
email_service = EmailService()


# ============= API ENDPOINTS =============

@app.route('/')
def index():
    """Web-UI Home."""
    return render_template('index.html')


@app.route('/api/status')
def status():
    """System-Status."""
    return jsonify({
        'status': 'running',
        'products': len(tracker.products),
        'brands': len(tracker.brands),
        'tracked_stores': TRACKED_STORES,
        'last_update': datetime.now().isoformat()
    })


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Triggert manuellen Scan."""
    try:
        logger.info("API: Manueller Scan gestartet")
        
        results = []
        for store_slug in TRACKED_STORES:
            try:
                scraper = MarktguruScraper(zip_code=ZIP_CODE, retailer_slug=store_slug)
                offers = scraper.run()
                
                if offers:
                    for offer in offers:
                        tracker.add_or_update_product(offer)
                    results.append({
                        'store': store_slug,
                        'offers': len(offers),
                        'status': 'success'
                    })
            except Exception as e:
                logger.error(f"Fehler bei {store_slug}: {e}")
                results.append({
                    'store': store_slug,
                    'error': str(e),
                    'status': 'error'
                })
        
        tracker.save_all()
        
        # Deal-Sniper ausführen
        deals = sniper.scan_for_deals(tracker)
        
        return jsonify({
            'status': 'success',
            'scan_results': results,
            'deals_found': len(deals),
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Scan-Fehler: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/products')
def get_products():
    """Gibt alle Produkte zurück."""
    limit = request.args.get('limit', 100, type=int)
    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    
    products = []
    for prod_id, prod in tracker.products.items():
        # Filter
        if search and search not in prod['normalized_name']:
            continue
        if category and prod['category'] != category:
            continue
        
        brand = tracker.brands.get(prod['brand_id'], {})
        
        products.append({
            'id': prod_id,
            'name': prod['name'],
            'brand': brand.get('name', ''),
            'category': prod['category'],
            'stores': prod['stores_available'],
            'observations': prod['total_observations']
        })
    
    return jsonify({
        'products': products[:limit],
        'total': len(products)
    })


@app.route('/api/products/<product_id>')
def get_product_detail(product_id):
    """Detaillierte Produkt-Info."""
    report = tracker.get_product_report(product_id)
    
    if not report:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify(report)


@app.route('/api/deals')
def get_deals():
    """Gibt Top-Deals zurück."""
    limit = request.args.get('limit', 10, type=int)
    deals = tracker.get_top_deals(limit=limit)
    
    return jsonify({'deals': deals})


@app.route('/api/expiring')
def get_expiring():
    """Gibt ablaufende Angebote zurück."""
    days = request.args.get('days', 3, type=int)
    expiring = tracker.get_expiring_soon(days=days)
    
    return jsonify({'expiring': expiring})


@app.route('/api/sniper/rules')
def get_sniper_rules():
    """Gibt Sniper-Regeln zurück."""
    return jsonify(sniper.rules)


@app.route('/api/sniper/alerts')
def get_sniper_alerts():
    """Gibt heutige Sniper-Alerts zurück."""
    alerts = sniper.get_alerts_today()
    return jsonify({'alerts': alerts, 'count': len(alerts)})


@app.route('/api/sniper/add-price-alert', methods=['POST'])
def add_price_alert():
    """Fügt Preis-Alert hinzu."""
    data = request.json
    
    pattern = data.get('pattern')
    max_price = data.get('max_price')
    store = data.get('store')
    
    if not pattern or max_price is None:
        return jsonify({'error': 'Missing parameters'}), 400
    
    alert_id = sniper.add_price_alert(pattern, float(max_price), store)
    
    return jsonify({
        'status': 'success',
        'alert_id': alert_id,
        'message': f'Price alert created for "{pattern}"'
    })


@app.route('/api/sniper/add-category-alert', methods=['POST'])
def add_category_alert():
    """Fügt Kategorie-Alert hinzu."""
    data = request.json
    
    category = data.get('category')
    max_unit_price = data.get('max_unit_price')
    unit = data.get('unit', 'kg')
    
    if not category or max_unit_price is None:
        return jsonify({'error': 'Missing parameters'}), 400
    
    alert_id = sniper.add_category_alert(category, float(max_unit_price), unit)
    
    return jsonify({
        'status': 'success',
        'alert_id': alert_id,
        'message': f'Category alert created for "{category}"'
    })


@app.route('/api/stats')
def get_stats():
    """Gibt Statistiken zurück."""
    categories = {}
    for prod in tracker.products.values():
        cat = prod['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    top_brands = sorted(
        [b for b in tracker.brands.values() if b.get('product_count', 0) > 0],
        key=lambda x: x['product_count'],
        reverse=True
    )[:10]
    
    return jsonify({
        'total_products': len(tracker.products),
        'total_brands': len(tracker.brands),
        'categories': categories,
        'top_brands': [{'name': b['name'], 'count': b['product_count']} for b in top_brands]
    })

@app.route('/api/sniper/delete-alert', methods=['POST'])
def delete_sniper_alert():
    """Löscht Sniper-Alert."""
    data = request.json
    
    alert_type = data.get('type')
    alert_id = data.get('id')
    
    if not alert_type or alert_id is None:
        return jsonify({'error': 'Missing parameters'}), 400
    
    success = sniper.remove_alert(alert_type, int(alert_id))
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'Alert #{alert_id} deleted'
        })
    else:
        return jsonify({'error': 'Alert not found'}), 404

@app.route('/api/products/<product_id>/price-history')
def get_price_history(product_id):
    """Gibt Preisverlauf für ein Produkt zurück."""
    if product_id not in tracker.price_history:
        return jsonify({'error': 'Product not found'}), 404
    
    history_by_store = tracker.price_history[product_id]
    product = tracker.products.get(product_id, {})
    brand = tracker.brands.get(product.get('brand_id'), {})
    
    # Formatiere Daten für Chart
    chart_data = {}
    
    for store, history in history_by_store.items():
        dates = []
        prices = []
        unit_prices = []
        
        for entry in history:
            dates.append(entry['date'])
            prices.append(entry['price'])
            unit_prices.append(entry['unit_price'])
        
        chart_data[store] = {
            'dates': dates,
            'prices': prices,
            'unit_prices': unit_prices
        }
    
    return jsonify({
        'product_id': product_id,
        'product_name': product.get('name', ''),
        'brand': brand.get('name', ''),
        'category': product.get('category', ''),
        'base_unit': product.get('base_unit', 'kg'),
        'chart_data': chart_data,
        'observations': product.get('total_observations', 0)
    })

# ============= FAVORITES ENDPOINTS =============

@app.route('/api/favorites')
def get_favorites():
    """Gibt alle Favoriten zurück."""
    detailed = favorites.get_favorites_with_details(tracker)
    return jsonify({
        'favorites': detailed,
        'count': len(detailed)
    })


@app.route('/api/favorites/add', methods=['POST'])
def add_favorite():
    """Fügt Produkt zu Favoriten hinzu."""
    data = request.json
    product_id = data.get('product_id')
    user_note = data.get('note', '')
    
    if not product_id:
        return jsonify({'error': 'Missing product_id'}), 400
    
    # Prüfe ob Produkt existiert
    if product_id not in tracker.products:
        return jsonify({'error': 'Product not found'}), 404
    
    success = favorites.add_favorite(product_id, user_note)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Zu Favoriten hinzugefügt'
        })
    else:
        return jsonify({
            'status': 'info',
            'message': 'Bereits in Favoriten'
        })


@app.route('/api/favorites/remove', methods=['POST'])
def remove_favorite():
    """Entfernt Produkt aus Favoriten."""
    data = request.json
    product_id = data.get('product_id')
    
    if not product_id:
        return jsonify({'error': 'Missing product_id'}), 400
    
    success = favorites.remove_favorite(product_id)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Aus Favoriten entfernt'
        })
    else:
        return jsonify({'error': 'Not in favorites'}), 404


@app.route('/api/favorites/check/<product_id>')
def check_favorite(product_id):
    """Prüft ob Produkt Favorit ist."""
    is_fav = favorites.is_favorite(product_id)
    return jsonify({'is_favorite': is_fav})


@app.route('/api/favorites/update-note', methods=['POST'])
def update_favorite_note():
    """Aktualisiert Notiz für Favorit."""
    data = request.json
    product_id = data.get('product_id')
    note = data.get('note', '')
    
    if not product_id:
        return jsonify({'error': 'Missing product_id'}), 400
    
    success = favorites.update_note(product_id, note)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Notiz aktualisiert'
        })
    else:
        return jsonify({'error': 'Not in favorites'}), 404


@app.route('/api/favorites/stats')
def get_favorites_stats():
    """Gibt Statistiken über Favoriten zurück."""
    detailed = favorites.get_favorites_with_details(tracker)
    
    if not detailed:
        return jsonify({
            'total_favorites': 0,
            'avg_savings': 0,
            'on_sale_count': 0
        })
    
    # Berechne Durchschnitts-Ersparnis
    total_savings = 0
    on_sale_count = 0
    
    for fav in detailed:
        if fav['current_prices'] and len(fav['current_prices']) > 1:
            prices = [p['unit_price'] for p in fav['current_prices'].values()]
            if len(prices) > 1:
                avg = sum(prices) / len(prices)
                min_price = min(prices)
                savings = ((avg - min_price) / avg) * 100
                total_savings += savings
                on_sale_count += 1
    
    avg_savings = total_savings / len(detailed) if detailed else 0
    
    return jsonify({
        'total_favorites': len(detailed),
        'avg_savings': round(avg_savings, 1),
        'on_sale_count': on_sale_count
    })

@app.route('/api/compare')
def compare_products():
    """Vergleicht Preise über alle Stores für Produkte."""
    search_query = request.args.get('search', '').lower()
    limit = int(request.args.get('limit', 50))
    
    if not search_query or len(search_query) < 2:
        return jsonify({'error': 'Search query too short (min 2 characters)'}), 400
    
    # Finde passende Produkte
    matching_products = {}
    
    for product_id, product in tracker.products.items():
        if search_query in product['name'].lower():
            # Normalisiere Produktname für Gruppierung
            base_name = product['name'].lower()
            
            # Entferne Store-spezifische Marker
            for marker in ['rewe', 'lidl', 'aldi', 'kaufland', 'ja!', 'gut&günstig']:
                base_name = base_name.replace(marker, '').strip()
            
            if base_name not in matching_products:
                matching_products[base_name] = {
                    'name': product['name'],
                    'brand': tracker.brands.get(product['brand_id'], {}).get('name', ''),
                    'category': product['category'],
                    'base_unit': product['base_unit'],
                    'stores': {},
                    'best_price': float('inf'),
                    'best_store': None,
                    'worst_price': 0,
                    'worst_store': None,
                    'avg_price': 0
                }
            
            # Hole aktuelle Preise für dieses Produkt
            if product_id in tracker.price_history:
                today = datetime.now().strftime("%Y-%m-%d")
                
                for store, history in tracker.price_history[product_id].items():
                    if history and history[-1]['date'] == today:
                        latest = history[-1]
                        unit_price = latest['unit_price']
                        
                        # Speichere besten Preis pro Store
                        if store not in matching_products[base_name]['stores'] or \
                           unit_price < matching_products[base_name]['stores'][store]['unit_price']:
                            
                            matching_products[base_name]['stores'][store] = {
                                'product_id': product_id,
                                'price': latest['price'],
                                'unit_price': unit_price,
                                'quantity': product.get('quantity', ''),
                                'valid_until': latest.get('valid_until', '')
                            }
    
    # Berechne Statistiken
    comparison_results = []
    
    for base_name, data in matching_products.items():
        if not data['stores']:
            continue
        
        # Finde Best/Worst
        unit_prices = [(store, info['unit_price']) for store, info in data['stores'].items()]
        unit_prices.sort(key=lambda x: x[1])
        
        data['best_store'] = unit_prices[0][0]
        data['best_price'] = unit_prices[0][1]
        data['worst_store'] = unit_prices[-1][0]
        data['worst_price'] = unit_prices[-1][1]
        data['avg_price'] = sum(p[1] for p in unit_prices) / len(unit_prices)
        data['savings'] = data['worst_price'] - data['best_price']
        data['savings_percent'] = round((data['savings'] / data['worst_price']) * 100, 1) if data['worst_price'] > 0 else 0
        data['available_in'] = len(data['stores'])
        
        comparison_results.append(data)
    
    # Sortiere nach Anzahl verfügbarer Stores (interessanteste zuerst)
    comparison_results.sort(key=lambda x: x['available_in'], reverse=True)
    
    return jsonify({
        'query': search_query,
        'results': comparison_results[:limit],
        'total_found': len(comparison_results)
    })


@app.route('/api/compare/product/<product_id>')
def compare_single_product(product_id):
    """Vergleicht einen spezifischen Produkt über alle Stores."""
    if product_id not in tracker.products:
        return jsonify({'error': 'Product not found'}), 404
    
    product = tracker.products[product_id]
    brand = tracker.brands.get(product['brand_id'], {})
    
    stores_data = {}
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Sammle Preise von allen Stores
    if product_id in tracker.price_history:
        for store, history in tracker.price_history[product_id].items():
            if history and history[-1]['date'] == today:
                latest = history[-1]
                stores_data[store] = {
                    'price': latest['price'],
                    'unit_price': latest['unit_price'],
                    'quantity': product.get('quantity', ''),
                    'valid_until': latest.get('valid_until', '')
                }
    
    if not stores_data:
        return jsonify({
            'error': 'No current prices available',
            'product_name': product['name']
        }), 404
    
    # Statistiken
    unit_prices = list(stores_data.values())
    best_store = min(stores_data.items(), key=lambda x: x[1]['unit_price'])
    worst_store = max(stores_data.items(), key=lambda x: x[1]['unit_price'])
    avg_price = sum(s['unit_price'] for s in unit_prices) / len(unit_prices)
    
    return jsonify({
        'product_id': product_id,
        'name': product['name'],
        'brand': brand.get('name', ''),
        'category': product['category'],
        'base_unit': product['base_unit'],
        'stores': stores_data,
        'best_store': best_store[0],
        'best_price': best_store[1]['unit_price'],
        'worst_store': worst_store[0],
        'worst_price': worst_store[1]['unit_price'],
        'avg_price': avg_price,
        'savings': worst_store[1]['unit_price'] - best_store[1]['unit_price'],
        'savings_percent': round(((worst_store[1]['unit_price'] - best_store[1]['unit_price']) / worst_store[1]['unit_price']) * 100, 1) if worst_store[1]['unit_price'] > 0 else 0
    })

# ============= EMAIL ENDPOINTS =============

@app.route('/api/email/test', methods=['POST'])
def test_email():
    """Sendet Test-Email."""
    success = email_service.send_test_email()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Test-Email wurde versendet! Prüfe dein Postfach.'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Email konnte nicht versendet werden. Prüfe Logs.'
        }), 500


@app.route('/api/email/weekly-report', methods=['POST'])
def send_weekly_report():
    """Sendet wöchentlichen Report manuell."""
    success = email_service.send_weekly_report(tracker, favorites)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Wöchentlicher Report wurde versendet!'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Report konnte nicht versendet werden.'
        }), 500


@app.route('/api/email/status')
def email_status():
    """Gibt Email-Service Status zurück."""
    return jsonify({
        'enabled': email_service.enabled,
        'from': email_service.from_email,
        'recipients': email_service.recipients,
        'configured': bool(email_service.password)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
