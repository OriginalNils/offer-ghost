import json
import logging
from typing import List, Dict, Set
from pathlib import Path

logger = logging.getLogger(__name__)

class FavoritesManager:
    """Verwaltet User-Favoriten"""
    
    def __init__(self, favorites_file: Path):
        self.favorites_file = favorites_file
        self.favorites = self._load()
    
    def _load(self) -> Dict[int, Set[str]]:
        """Lade Favoriten: {user_id: set(keywords)}"""
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert lists to sets
                    return {int(k): set(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Fehler beim Laden: {e}")
        return {}
    
    def _save(self):
        """Speichere Favoriten"""
        # Convert sets to lists for JSON
        data = {str(k): list(v) for k, v in self.favorites.items()}
        with open(self.favorites_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add(self, user_id: int, keyword: str) -> bool:
        """Füge Favorit hinzu"""
        if user_id not in self.favorites:
            self.favorites[user_id] = set()
        
        keyword_lower = keyword.lower().strip()
        
        if keyword_lower in self.favorites[user_id]:
            return False
        
        self.favorites[user_id].add(keyword_lower)
        self._save()
        logger.info(f"➕ User {user_id} added favorite: {keyword_lower}")
        return True
    
    def remove(self, user_id: int, keyword: str) -> bool:
        """Entferne Favorit"""
        if user_id not in self.favorites:
            return False
        
        keyword_lower = keyword.lower().strip()
        
        if keyword_lower not in self.favorites[user_id]:
            return False
        
        self.favorites[user_id].remove(keyword_lower)
        self._save()
        logger.info(f"➖ User {user_id} removed favorite: {keyword_lower}")
        return True
    
    def get(self, user_id: int) -> List[str]:
        """Hole Favoriten eines Users"""
        return sorted(list(self.favorites.get(user_id, set())))
    
    def match_deals(self, user_id: int, deals: List[Dict]) -> List[Dict]:
        """Finde Deals die zu Favoriten passen"""
        keywords = self.favorites.get(user_id, set())
        
        if not keywords:
            return []
        
        matched = []
        for deal in deals:
            name_lower = deal.get("name", "").lower()
            desc_lower = deal.get("description", "").lower()
            
            for keyword in keywords:
                if keyword in name_lower or keyword in desc_lower:
                    matched.append(deal)
                    break
        
        return matched
    
    def clear(self, user_id: int):
        """Lösche alle Favoriten eines Users"""
        if user_id in self.favorites:
            del self.favorites[user_id]
            self._save()
