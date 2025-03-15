import asyncio
import json
from pathlib import Path
import sys
from typing import List, Dict, Any
from datetime import datetime

from .config.settings import config
from .core.models import Recipe
from .core.enricher import RecipeEnricher

def parse_recipe_json(data: Dict[str, Any]) -> Recipe:
    """Parse a single recipe JSON data into a Recipe object."""
    # Convert publish_date string to datetime if present
    if "publish_date" in data and data["publish_date"]:
        try:
            data["publish_date"] = datetime.fromisoformat(data["publish_date"].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            data["publish_date"] = None
    
    # Create Recipe object
    return Recipe(**data)

async def load_recipes(file_path: Path) -> List[Recipe]:
    """Load recipes from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Handle both single recipe and list of recipes
        if isinstance(data, dict):
            data = [data]
            
        recipes = []
        for recipe_data in data:
            try:
                recipe = parse_recipe_json(recipe_data)
                recipes.append(recipe)
            except Exception as e:
                print(f"Error parsing recipe: {recipe_data.get('title', 'Unknown')}: {str(e)}")
                continue
                
        return recipes
        
    except Exception as e:
        print(f"Error loading recipes: {str(e)}")
        sys.exit(1)

async def main():
    """Main function to run the recipe enrichment process."""
    try:
        # Ensure OpenAI API key is set
        if not config.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        # Create output directory
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load recipes
        print(f"Loading recipes from {config.INPUT_FILE}")
        recipes = await load_recipes(config.INPUT_FILE)
        print(f"Loaded {len(recipes)} recipes")
        
        # Initialize enricher
        enricher = RecipeEnricher()
        
        # Process recipes in batches
        enriched_recipes = []
        for i in range(0, len(recipes), config.BATCH_SIZE):
            batch = recipes[i:i + config.BATCH_SIZE]
            batch_enriched = await enricher.enrich_recipes(batch)
            enriched_recipes.extend(batch_enriched)
            
            # Save intermediate results
            output_file = config.OUTPUT_DIR / f"enriched_recipes_batch_{i//config.BATCH_SIZE}.json"
            enricher.save_enriched_recipes(batch_enriched, output_file)
        
        # Save final results
        final_output = config.OUTPUT_DIR / "enriched_recipes_final.json"
        enricher.save_enriched_recipes(enriched_recipes, final_output)
        print(f"Enrichment complete. Results saved to {final_output}")
        
    except Exception as e:
        print(f"Error during recipe enrichment: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 