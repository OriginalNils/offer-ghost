import json
import logging
from datetime import datetime
from typing import List, Dict, Set
from pathlib import Path

logger = logging.getLogger(__name__)

class DealManager:
    """Verwaltet alle Deals und erkennt neue"""
    
    def __init__(self, deals_file: Path, history_file: Path, min_discount: int = 15):
        self.deals_file = deals_file
        self.history_file = history_file
        self.min_discount = min_discount
        self.current_deals = []
        self.deal_ids_seen = self._load_history()
        
    def _load_history(self) -> Set[str]:
        """Lade bereits gesehene Deal-IDs"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("seen_ids", []))
            except:
                pass
        return set()
    
    def _save_history(self):
        """Speichere gesehene Deal-IDs"""
        data = {
            "seen_ids": list(self.deal_ids_seen),
            "last_update": datetime.now().isoformat()
        }
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def update_deals(self, new_deals: List[Dict]) -> Dict:
        """Update Deals und finde neue"""
        # Filter nach Mindest-Rabatt
        filtered_deals = [
            d for d in new_deals 
            if d.get("discount_percent", 0) >= self.min_discount
        ]
        
        # Finde neue Deals
        new_deal_ids = set()
        new_deals_list = []
        
        for deal in filtered_deals:
            deal_id = f"{deal['store']}_{deal['id']}"
            
            if deal_id not in self.deal_ids_seen:
                new_deal_ids.add(deal_id)
                new_deals_list.append(deal)
                self.deal_ids_seen.add(deal_id)
        
        # Speichere aktuelle Deals
        self.current_deals = filtered_deals
        self._save_deals()
        self._save_history()
        
        logger.info(f"📊 Deals aktualisiert: {len(filtered_deals)} gesamt, {len(new_deals_list)} neu")
        
        return {
            "total": len(filtered_deals),
            "new": len(new_deals_list),
            "new_deals": new_deals_list
        }
    
    def _save_deals(self):
        """Speichere aktuelle Deals"""
        data = {
            "deals": self.current_deals,
            "last_update": datetime.now().isoformat(),
            "count": len(self.current_deals)
        }
        with open(self.deals_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_deals(self, category: str = None, store: str = None, min_discount: int = None) -> List[Dict]:
        """Hole Deals mit optionalen Filtern"""
        deals = self.current_deals.copy()
        
        if category:
            deals = [d for d in deals if d.get("category", "").lower() == category.lower()]
        
        if store:
            deals = [d for d in deals if d.get("store", "").lower() == store.lower()]
        
        if min_discount:
            deals = [d for d in deals if d.get("discount_percent", 0) >= min_discount]
        
        return deals
    
    def get_top_deals(self, limit: int = 10) -> List[Dict]:
        """Hole Top-Deals nach Rabatt"""
        sorted_deals = sorted(
            self.current_deals, 
            key=lambda x: x.get("discount_percent", 0), 
            reverse=True
        )
        return sorted_deals[:limit]
    
    def get_stats(self) -> Dict:
        """Statistiken"""
        if not self.current_deals:
            return {
                "total_deals": 0,
                "stores": [],
                "categories": {},
                "avg_discount": 0,
                "max_discount": 0
            }
        
        stores = list(set(d["store"] for d in self.current_deals))
        
        categories = {}
        for deal in self.current_deals:
            cat = deal.get("category", "Sonstiges")
            categories[cat] = categories.get(cat, 0) + 1
        
        discounts = [d.get("discount_percent", 0) for d in self.current_deals]
        
        return {
            "total_deals": len(self.current_deals),
            "stores": stores,
            "categories": categories,
            "avg_discount": round(sum(discounts) / len(discounts)),
            "max_discount": max(discounts)
        }
