from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import os
import logging
from datetime import datetime

from src.config import DATA_DIR, ZIP_CODE, TRACKED_STORES
from src.core.product_tracker import ProductTracker
from src.core.deal_sniper import DealSniper
from src.scrapers.marktguru import MarktguruScraper

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
