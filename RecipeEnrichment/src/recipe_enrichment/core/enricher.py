import json
from pathlib import Path
from typing import List, Dict, Any
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import openai
import anthropic
import google.generativeai as genai
from abc import ABC, abstractmethod
from tqdm import tqdm

from ..config.settings import config, ModelType
from .models import Recipe, RecipeEnrichment, EnrichmentPrompt
from .cache import RecipeCache

class BaseRecipeEnricher(ABC):
    """Abstract base class for recipe enrichment."""
    
    def __init__(self):
        self.prompt = EnrichmentPrompt()
        self._setup_logging()
        self.cache = RecipeCache()
    
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
    
    @abstractmethod
    async def _call_llm_api(self, system_message: str, user_message: str) -> str:
        """Call the LLM API and return the response content."""
        pass

    @retry(stop=stop_after_attempt(config.MAX_RETRIES),
           wait=wait_exponential(multiplier=config.RETRY_DELAY))
    async def _enrich_single_recipe(self, recipe: Recipe) -> Recipe:
        """Enrich a single recipe using the LLM API."""
        try:
            # Check cache first
            cached_data = self.cache.get(recipe, config.MODEL_TYPE)
            if cached_data:
                self.logger.info(f"Using cached enrichment for recipe: {recipe.title}")
                recipe.enrichment = RecipeEnrichment(**cached_data)
                return recipe
            
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
            
            # Call LLM API
            response_content = await self._call_llm_api(
                self.prompt.system_message,
                formatted_prompt
            )
            
            # Check if response contains an error message (from our error handling)
            if response_content.startswith('{"error":'):
                error_data = json.loads(response_content)
                self.logger.error(f"Error in LLM response: {error_data.get('error')}")
                raise ValueError(f"Error in LLM response: {error_data.get('error')}")
            
            # Parse the response with proper Unicode handling
            try:
                enrichment_data = json.loads(response_content, strict=False)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Response content: {response_content}")
                raise
            
            # Fix any Unicode escape sequences in strings
            for key, value in enrichment_data.items():
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    enrichment_data[key] = [self._fix_unicode(item) for item in value]
                elif isinstance(value, str):
                    enrichment_data[key] = self._fix_unicode(value)
            
            # Add URL fields from the original recipe
            enrichment_data["recipe_url"] = recipe.url
            
            # Add image URL (main image)
            if hasattr(recipe, 'top_image') and recipe.top_image:
                enrichment_data["image_url"] = recipe.top_image
            elif hasattr(recipe, 'meta_img') and recipe.meta_img:
                enrichment_data["image_url"] = recipe.meta_img
            elif hasattr(recipe, 'images') and recipe.images and len(recipe.images) > 0:
                enrichment_data["image_url"] = recipe.images[0]
            
            # Add video URL
            if hasattr(recipe, 'movies') and recipe.movies and len(recipe.movies) > 0:
                enrichment_data["video_url"] = recipe.movies[0]
            
            # Add additional images
            if hasattr(recipe, 'images') and recipe.images and len(recipe.images) > 0:
                # Skip the first image if it's already used as the main image
                if enrichment_data.get("image_url") == recipe.images[0] and len(recipe.images) > 1:
                    enrichment_data["additional_images"] = recipe.images[1:]
                else:
                    enrichment_data["additional_images"] = recipe.images
            
            # Preserve original categories from the input recipe
            if recipe.categories:
                enrichment_data["original_categories"] = recipe.categories
            else:
                enrichment_data["original_categories"] = []
            
            # Add default meal prep guidance if not provided by the model
            if "meal_prep_guidance" not in enrichment_data:
                enrichment_data["meal_prep_guidance"] = {
                    "components_to_prep": [],
                    "prep_instructions": {},
                    "storage_info": {},
                    "final_assembly": "Prepare the recipe as instructed.",
                    "time_saving_tips": ["No specific meal prep guidance available for this recipe."]
                }
            
            # Ensure all required fields are present
            required_fields = [
                "title", "generated_summary", "ingredients", "instructions",
                "healthiness_score", "ease_of_cooking_score", "indian_ingredient_availability_score",
                "prep_time_minutes", "prep_time_breakdown", "total_cooking_time_minutes",
                "cooking_time_breakdown", "protein_level", "meal_type_suitability",
                "dietary_restrictions", "categories"
            ]
            
            missing_fields = [field for field in required_fields if field not in enrichment_data]
            if missing_fields:
                self.logger.warning(f"Missing required fields in enrichment data: {missing_fields}")
                # Add default values for missing fields
                for field in missing_fields:
                    if field in ["title", "generated_summary"]:
                        enrichment_data[field] = recipe.title if field == "title" else f"A recipe for {recipe.title}"
                    elif field in ["ingredients", "instructions", "meal_type_suitability", "dietary_restrictions"]:
                        enrichment_data[field] = recipe.ingredients if field == "ingredients" else (
                            recipe.instructions if field == "instructions" else []
                        )
                    elif field in ["healthiness_score", "ease_of_cooking_score", "indian_ingredient_availability_score", "protein_level"]:
                        enrichment_data[field] = "Moderate" if field != "protein_level" else "Medium"
                    elif field in ["prep_time_minutes", "total_cooking_time_minutes", "soaking_time_minutes"]:
                        enrichment_data[field] = 30 if field != "soaking_time_minutes" else 0
                    elif field in ["prep_time_breakdown", "cooking_time_breakdown", "categories"]:
                        enrichment_data[field] = {"default": "Not provided"}
            
            # Use the model's extracted ingredients and instructions with preserved style
            # (no longer overriding with original data)
            
            # Cache the enrichment data
            self.cache.set(recipe, config.MODEL_TYPE, enrichment_data)
            
            recipe.enrichment = RecipeEnrichment(**enrichment_data)
            
            return recipe
            
        except Exception as e:
            self.logger.error(f"Error enriching recipe {recipe.title}: {str(e)}")
            raise

    def _fix_unicode(self, text: str) -> str:
        """Fix Unicode escape sequences in text."""
        # Replace common Unicode escape sequences with their actual characters
        replacements = {
            "\\u00bd": "½",
            "\\u00bc": "¼",
            "\\u00be": "¾",
            "\\u2153": "⅓",
            "\\u2154": "⅔",
            "\\u2155": "⅕",
            "\\u2156": "⅖",
            "\\u2157": "⅗",
            "\\u2158": "⅘",
            "\\u2159": "⅙",
            "\\u215a": "⅚",
            "\\u215b": "⅛",
            "\\u215c": "⅜",
            "\\u215d": "⅝",
            "\\u215e": "⅞"
        }
        
        for escape_seq, char in replacements.items():
            text = text.replace(escape_seq, char)
        
        return text

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

class OpenAIRecipeEnricher(BaseRecipeEnricher):
    """Recipe enricher using OpenAI's API."""
    
    def __init__(self):
        super().__init__()
        if not config.openai_token:
            raise ValueError("OpenAI API token not found")
        self.client = openai.OpenAI(api_key=config.openai_token)
    
    async def _call_llm_api(self, system_message: str, user_message: str) -> str:
        """Call OpenAI API and return the response content."""
        response = self.client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content

class ClaudeRecipeEnricher(BaseRecipeEnricher):
    """Recipe enricher using Anthropic's Claude API."""
    
    def __init__(self):
        super().__init__()
        if not config.anthropic_token:
            raise ValueError("Anthropic API token not found")
        self.client = anthropic.Anthropic(api_key=config.anthropic_token)
    
    async def _call_llm_api(self, system_message: str, user_message: str) -> str:
        """Call Claude API and return the response content."""
        response = self.client.messages.create(
            model=config.MODEL_NAME,
            max_tokens=4096,
            system=system_message,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        return response.content[0].text

class GeminiRecipeEnricher(BaseRecipeEnricher):
    """Recipe enricher using Google's Gemini API."""
    
    def __init__(self):
        super().__init__()
        if not config.google_token:
            raise ValueError("Google API token not found")
        genai.configure(api_key=config.google_token)
        self.model = genai.GenerativeModel(config.MODEL_NAME)
        
        # Custom prompt for Gemini to encourage more enticing summaries
        self.gemini_system_message = """You are a culinary expert AI assistant specializing in recipe analysis and enrichment. Your task is to analyze recipe data and extract structured information.

RULES:
1. Extract and clean the ingredients and instructions from the input data.
2. Create clean, numbered lists for ingredients and instructions.
3. Generate a creative, enticing, and unique summary of the recipe (2-3 sentences maximum) that will make the reader want to cook this recipe. Avoid starting with common and predictable phrases like "Craving a...", "Looking for a...", "This recipe is...", "Imagine biting into...", or similar generic openings. Aim for variety in tone and focus. Highlight a key appealing aspect of the dish, such as its flavor profile, ease of preparation, health benefits, or unique ingredients.
4. Analyze the recipe for healthiness, ease of cooking, and ingredient availability. 
5. Estimate preparation and cooking times based on the recipe steps.
6. Categorize the recipe appropriately, providing both structured categories and detailed categorization.
7. DO NOT modify the ingredients or instructions. Use them exactly as provided in the input.
8. Preserve all URLs from the original recipe (recipe page URL, image URLs, video URLs).
9. Format all numerical values consistently.
10. Provide detailed meal prep guidance for components that can be prepared ahead of time.
11. Respond ONLY with a valid JSON object containing the requested fields.

For categories, provide a detailed structured object with arrays for each category type (meal_type, dish_type, cooking_method, region, cuisine_type, main_ingredients, special_occasion). Be comprehensive and include multiple values where appropriate. For example, a dish might belong to multiple meal types or use several cooking methods.

Your output must be a SINGLE, valid JSON object with no additional text before or after."""
    
    async def _call_llm_api(self, system_message: str, user_message: str) -> str:
        """Call Gemini API and return the response content."""
        try:
            # Use the custom Gemini system message instead of the standard one
            combined_prompt = f"{self.gemini_system_message}\n\n{user_message}\n\nIMPORTANT: Your response MUST be a valid JSON object and nothing else."
            
            # Set generation config to ensure we get a proper JSON response
            generation_config = {
                # Let the API use its default temperature
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]
            
            response = self.model.generate_content(
                combined_prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Check if response is empty
            if not response.text or response.text.strip() == "":
                self.logger.error("Gemini returned an empty response")
                # Return a minimal valid JSON with error message
                return '{"error": "Gemini returned an empty response"}'
            
            # Try to extract JSON from the response
            response_text = response.text.strip()
            
            # If response starts with ``` (markdown code block), extract the content
            if response_text.startswith("```json"):
                # Extract content between ```json and ```
                json_start = response_text.find("```json") + 7
                json_end = response_text.rfind("```")
                if json_end > json_start:
                    response_text = response_text[json_start:json_end].strip()
            elif response_text.startswith("```"):
                # Extract content between ``` and ```
                json_start = response_text.find("```") + 3
                json_end = response_text.rfind("```")
                if json_end > json_start:
                    response_text = response_text[json_start:json_end].strip()
            
            # Validate JSON
            try:
                json.loads(response_text)
                return response_text
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON from Gemini: {e}")
                self.logger.error(f"Response text: {response_text}")
                # Return a minimal valid JSON with error message
                return '{"error": "Gemini returned invalid JSON", "original_response": "' + response_text.replace('"', '\\"') + '"}'
                
        except Exception as e:
            self.logger.error(f"Error calling Gemini API: {str(e)}")
            # Return a minimal valid JSON with error message
            return '{"error": "Error calling Gemini API: ' + str(e).replace('"', '\\"') + '"}'

def create_enricher() -> BaseRecipeEnricher:
    """Factory function to create the appropriate enricher based on config."""
    if config.MODEL_TYPE == ModelType.GPT4:
        return OpenAIRecipeEnricher()
    elif config.MODEL_TYPE == ModelType.CLAUDE:
        return ClaudeRecipeEnricher()
    elif config.MODEL_TYPE == ModelType.GEMINI:
        return GeminiRecipeEnricher()
    else:
        raise ValueError(f"Unsupported model type: {config.MODEL_TYPE}") 