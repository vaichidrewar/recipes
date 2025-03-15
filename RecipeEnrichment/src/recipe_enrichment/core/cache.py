import json
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from ..config.settings import config, ModelType
from .models import Recipe

class RecipeCache:
    """Cache for enriched recipes to avoid redundant API calls."""
    
    def __init__(self, cache_dir: Path = None):
        """Initialize the cache with a directory path."""
        self.cache_dir = cache_dir or Path(config.OUTPUT_DIR) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def _generate_cache_key(self, recipe: Recipe, model_type: ModelType) -> str:
        """Generate a unique cache key based on recipe title, content, and model type."""
        # Create a hash of the recipe content to detect changes
        content_hash = hashlib.md5(
            json.dumps({
                "title": recipe.title,
                "ingredients": recipe.ingredients,
                "instructions": recipe.instructions,
                "text": recipe.text
            }, sort_keys=True).encode()
        ).hexdigest()
        
        # Combine title, content hash, and model type for the final key
        key = f"{recipe.title}_{content_hash}_{model_type.value}"
        
        # Make the key filesystem-friendly
        key = key.replace(" ", "_").replace("/", "_").replace("\\", "_")
        key = key.replace(":", "_").replace("*", "_").replace("?", "_")
        key = key.replace("\"", "_").replace("<", "_").replace(">", "_")
        key = key.replace("|", "_")
        
        return key
    
    def get(self, recipe: Recipe, model_type: ModelType) -> Optional[Dict[str, Any]]:
        """Get cached enrichment data for a recipe if it exists."""
        try:
            cache_key = self._generate_cache_key(recipe, model_type)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            if cache_file.exists():
                self.logger.info(f"Cache hit for recipe: {recipe.title}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            self.logger.info(f"Cache miss for recipe: {recipe.title}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving from cache: {str(e)}")
            return None
    
    def set(self, recipe: Recipe, model_type: ModelType, enrichment_data: Dict[str, Any]) -> bool:
        """Store enrichment data in the cache."""
        try:
            cache_key = self._generate_cache_key(recipe, model_type)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(enrichment_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Cached enrichment data for recipe: {recipe.title}")
            return True
        except Exception as e:
            self.logger.error(f"Error storing in cache: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """Clear all cached data."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            self.logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")
            return False 