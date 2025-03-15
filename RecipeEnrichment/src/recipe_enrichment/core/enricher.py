import json
from pathlib import Path
from typing import List, Dict, Any
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import openai
from tqdm import tqdm

from ..config.settings import config
from .models import Recipe, RecipeEnrichment, EnrichmentPrompt

class RecipeEnricher:
    """Class responsible for enriching recipe data using OpenAI's API."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=config.openai_token)
        self.prompt = EnrichmentPrompt()
        self._setup_logging()
        
    def _setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    @retry(stop=stop_after_attempt(config.MAX_RETRIES),
           wait=wait_exponential(multiplier=config.RETRY_DELAY))
    async def _enrich_single_recipe(self, recipe: Recipe) -> Recipe:
        """Enrich a single recipe using the OpenAI API."""
        try:
            # Prepare the prompt with all available information
            formatted_prompt = self.prompt.user_message_template.format(
                title=recipe.title,
                summary=recipe.summary or "Not provided",
                keywords=", ".join(recipe.keywords) if recipe.keywords else "Not provided",
                tags=", ".join(recipe.tags) if recipe.tags else "Not provided",
                categories=", ".join(recipe.categories) if recipe.categories else "Not provided",
                text=recipe.text,
                ingredients="\n".join(recipe.ingredients),
                instructions="\n".join(recipe.instructions)
            )
            
            # Call OpenAI API (without await since it's not async)
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": self.prompt.system_message},
                    {"role": "user", "content": formatted_prompt}
                ]
            )
            
            # Parse the response
            enrichment_data = json.loads(response.choices[0].message.content)
            
            # Preserve original ingredients and instructions
            enrichment_data["ingredients"] = recipe.ingredients
            enrichment_data["instructions"] = recipe.instructions
            
            recipe.enrichment = RecipeEnrichment(**enrichment_data)
            
            return recipe
            
        except Exception as e:
            self.logger.error(f"Error enriching recipe {recipe.title}: {str(e)}")
            raise
    
    async def enrich_recipes(self, recipes: List[Recipe]) -> List[Recipe]:
        """Enrich a list of recipes."""
        enriched_recipes = []
        
        for recipe in tqdm(recipes, desc="Enriching recipes"):
            try:
                enriched_recipe = await self._enrich_single_recipe(recipe)
                enriched_recipes.append(enriched_recipe)
            except Exception as e:
                self.logger.error(f"Failed to enrich recipe {recipe.title}: {str(e)}")
                continue
        
        return enriched_recipes
    
    def save_enriched_recipes(self, recipes: List[Recipe], output_file: Path):
        """Save enriched recipes to a JSON file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(
                    [recipe.model_dump() for recipe in recipes],
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            self.logger.info(f"Saved enriched recipes to {output_file}")
        except Exception as e:
            self.logger.error(f"Error saving enriched recipes: {str(e)}")
            raise 