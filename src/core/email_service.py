"""
Email-Service für Offer Ghost Reports.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from src.config import *

logger = logging.getLogger(__name__)


class EmailService:
    """Verwaltet Email-Versand."""
    
    def __init__(self):
        self.enabled = EMAIL_ENABLED
        self.smtp_host = EMAIL_SMTP_HOST
        self.smtp_port = EMAIL_SMTP_PORT
        self.use_tls = EMAIL_USE_TLS
        self.from_email = EMAIL_FROM
        self.from_name = EMAIL_FROM_NAME
        self.password = EMAIL_PASSWORD
        self.recipients = EMAIL_RECIPIENTS
        
        if self.enabled and not self.password:
            logger.warning("Email enabled but no password configured!")
            self.enabled = False
        
        logger.info(f"EmailService initialisiert: {'Enabled' if self.enabled else 'Disabled'}")
    
    def send_email(self, subject, html_body, recipients=None):
        """Sendet eine Email."""
        if not self.enabled:
            logger.warning("Email service is disabled")
            return False
        
        if recipients is None:
            recipients = self.recipients
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ", ".join(recipients)
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Connect to SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def generate_weekly_report(self, tracker, favorites_manager):
        """Generiert HTML für wöchentlichen Report."""
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        # Sammle Daten
        total_products = len(tracker.products)
        total_brands = len(tracker.brands)
        
        # Top Deals der Woche (basierend auf Ersparnis)
        deals = []
        for product_id, product in tracker.products.items():
            if product_id in tracker.price_history:
                for store, history in tracker.price_history[product_id].items():
                    if len(history) >= 2:
                        recent_prices = [h['unit_price'] for h in history[-7:]]
                        if len(recent_prices) >= 2:
                            avg_price = sum(recent_prices) / len(recent_prices)
                            current_price = recent_prices[-1]
                            
                            if current_price < avg_price * 0.85:  # Min. 15% Rabatt
                                savings_percent = int(((avg_price - current_price) / avg_price) * 100)
                                brand = tracker.brands.get(product['brand_id'], {})
                                
                                deals.append({
                                    'name': product['name'],
                                    'brand': brand.get('name', ''),
                                    'store': store,
                                    'current_price': current_price,
                                    'avg_price': avg_price,
                                    'savings_percent': savings_percent,
                                    'base_unit': product['base_unit']
                                })
        
        # Sortiere nach Ersparnis
        deals.sort(key=lambda x: x['savings_percent'], reverse=True)
        top_deals = deals[:5]
        
        # Favoriten mit aktuellen Angeboten
        favorite_deals = []
        if hasattr(favorites_manager, 'favorites'):
            for fav in favorites_manager.favorites:
                product_id = fav['product_id']
                if product_id in tracker.products:
                    product = tracker.products[product_id]
                    brand = tracker.brands.get(product['brand_id'], {})
                    
                    # Prüfe ob im Angebot
                    if product_id in tracker.price_history:
                        for store, history in tracker.price_history[product_id].items():
                            if history:
                                latest = history[-1]
                                if latest['date'] == today.strftime("%Y-%m-%d"):
                                    favorite_deals.append({
                                        'name': product['name'],
                                        'brand': brand.get('name', ''),
                                        'store': store,
                                        'price': latest['unit_price'],
                                        'base_unit': product['base_unit']
                                    })
                                    break
        
        # Berechne Gesamt-Ersparnis (wenn du immer Best Price kaufst)
        total_savings = sum(d['avg_price'] - d['current_price'] for d in deals)
        
        # Generiere HTML
        html = self._generate_html_template(
            total_products=total_products,
            total_brands=total_brands,
            top_deals=top_deals,
            favorite_deals=favorite_deals[:5],
            total_savings=total_savings
        )
        
        return html
    
    def _generate_html_template(self, total_products, total_brands, top_deals, favorite_deals, total_savings):
        """Generiert HTML-Template für Report."""
        
        # Top Deals HTML
        deals_html = ""
        for i, deal in enumerate(top_deals, 1):
            deals_html += f"""
            <tr style="background: {'#1e293b' if i % 2 == 0 else '#141b2d'};">
                <td style="padding: 15px; border-bottom: 1px solid #334155;">
                    <strong style="color: #f1f5f9;">{deal['name']}</strong><br>
                    <span style="color: #94a3b8; font-size: 13px;">{deal['brand']} • {deal['store'].upper()}</span>
                </td>
                <td style="padding: 15px; border-bottom: 1px solid #334155; text-align: right;">
                    <span style="color: #818cf8; font-size: 20px; font-weight: bold;">{deal['current_price']:.2f}€</span>
                    <span style="color: #94a3b8; font-size: 12px;">/{deal['base_unit']}</span>
                </td>
                <td style="padding: 15px; border-bottom: 1px solid #334155; text-align: right;">
                    <span style="background: linear-gradient(135deg, #34d399, #10b981); color: white; padding: 6px 12px; border-radius: 12px; font-weight: bold; font-size: 13px;">
                        -{deal['savings_percent']}%
                    </span>
                </td>
            </tr>
            """
        
        # Favoriten HTML
        favorites_html = ""
        if favorite_deals:
            for fav in favorite_deals:
                favorites_html += f"""
                <li style="padding: 10px 0; border-bottom: 1px solid #334155;">
                    <strong style="color: #f1f5f9;">{fav['name']}</strong> 
                    <span style="color: #94a3b8;">({fav['brand']})</span><br>
                    <span style="color: #818cf8; font-weight: bold;">{fav['price']:.2f}€/{fav['base_unit']}</span> 
                    <span style="color: #94a3b8;">bei {fav['store'].upper()}</span>
                </li>
                """
        else:
            favorites_html = "<li style='color: #94a3b8;'>Keine Favoriten aktuell im Angebot</li>"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background: #0a0f1e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                
                <!-- Header -->
                <div style="text-align: center; margin-bottom: 40px;">
                    <div style="font-size: 60px; margin-bottom: 15px;">👻</div>
                    <h1 style="color: #f1f5f9; margin: 0 0 10px 0; font-size: 32px;">Offer Ghost</h1>
                    <p style="color: #94a3b8; margin: 0; font-size: 16px;">Dein Wöchentlicher Deal-Report</p>
                    <p style="color: #64748b; margin: 5px 0 0 0; font-size: 14px;">{datetime.now().strftime('%d.%m.%Y')}</p>
                </div>
                
                <!-- Stats Cards -->
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 40px;">
                    <div style="background: linear-gradient(135deg, #1e293b, #141b2d); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 16px; padding: 20px; text-align: center;">
                        <div style="font-size: 32px; color: #818cf8; font-weight: bold; margin-bottom: 8px;">{total_products}</div>
                        <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase;">Produkte</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #1e293b, #141b2d); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 16px; padding: 20px; text-align: center;">
                        <div style="font-size: 32px; color: #818cf8; font-weight: bold; margin-bottom: 8px;">{total_brands}</div>
                        <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase;">Marken</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #1e293b, #141b2d); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 16px; padding: 20px; text-align: center;">
                        <div style="font-size: 32px; color: #34d399; font-weight: bold; margin-bottom: 8px;">{len(top_deals)}</div>
                        <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase;">Top Deals</div>
                    </div>
                </div>
                
                <!-- Savings Banner -->
                {f'''
                <div style="background: linear-gradient(135deg, #34d399, #10b981); border-radius: 16px; padding: 25px; text-align: center; margin-bottom: 40px;">
                    <div style="font-size: 18px; color: white; margin-bottom: 10px;">💰 Potenzielle Ersparnis diese Woche</div>
                    <div style="font-size: 42px; color: white; font-weight: bold;">{total_savings:.2f}€</div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.8); margin-top: 10px;">Wenn du immer den besten Preis kaufst</div>
                </div>
                ''' if total_savings > 0 else ''}
                
                <!-- Top Deals -->
                <div style="background: linear-gradient(135deg, #1e293b, #141b2d); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 20px; padding: 25px; margin-bottom: 30px;">
                    <h2 style="color: #f1f5f9; margin: 0 0 20px 0; font-size: 22px;">🔥 Top 5 Deals der Woche</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        {deals_html if top_deals else '<tr><td style="padding: 20px; text-align: center; color: #94a3b8;">Keine Deals diese Woche gefunden</td></tr>'}
                    </table>
                </div>
                
                <!-- Favorites -->
                <div style="background: linear-gradient(135deg, #1e293b, #141b2d); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 20px; padding: 25px; margin-bottom: 30px;">
                    <h2 style="color: #f1f5f9; margin: 0 0 20px 0; font-size: 22px;">⭐ Deine Favoriten im Angebot</h2>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        {favorites_html}
                    </ul>
                </div>
                
                <!-- CTA Button -->
                <div style="text-align: center; margin: 40px 0;">
                    <a href="http://192.168.178.98:5000" style="display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 16px 40px; border-radius: 16px; text-decoration: none; font-weight: bold; font-size: 16px; box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);">
                        🚀 Offer Ghost öffnen
                    </a>
                </div>
                
                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 30px; border-top: 1px solid #334155;">
                    <p style="color: #64748b; font-size: 13px; margin: 0;">
                        Du erhältst diese Email weil du Offer Ghost nutzt.<br>
                        Report generiert am {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_weekly_report(self, tracker, favorites_manager):
        """Sendet wöchentlichen Report."""
        try:
            html = self.generate_weekly_report(tracker, favorites_manager)
            subject = f"📊 Dein Wöchentlicher Deal-Report - {datetime.now().strftime('%d.%m.%Y')}"
            
            success = self.send_email(subject, html)
            
            if success:
                logger.info("Weekly report sent successfully")
            else:
                logger.error("Failed to send weekly report")
            
            return success
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            return False
    
    def send_test_email(self):
        """Sendet Test-Email."""
        html = """
        <html>
        <body style="font-family: Arial; padding: 40px; background: #0a0f1e; color: #f1f5f9;">
            <div style="max-width: 600px; margin: 0 auto; background: #1e293b; padding: 40px; border-radius: 20px;">
                <div style="text-align: center; font-size: 60px; margin-bottom: 20px;">👻</div>
                <h1 style="text-align: center; color: #818cf8;">Offer Ghost Email Test</h1>
                <p style="text-align: center; color: #94a3b8; font-size: 18px;">
                    Email-Service funktioniert! 🎉<br>
                    Du bist bereit für wöchentliche Reports.
                </p>
                <div style="text-align: center; margin-top: 30px;">
                    <a href="http://192.168.178.98:5000" style="display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 14px 30px; border-radius: 12px; text-decoration: none; font-weight: bold;">
                        Zu Offer Ghost
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email("✅ Offer Ghost Email Test", html)
