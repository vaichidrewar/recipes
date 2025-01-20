from scrapegraphai.graphs import SmartScraperMultiGraph
from dataclasses import dataclass
from typing import Optional, List
import asyncio
import json
from config import Config
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

@dataclass
class Recipe:
    name: str
    cooking_time: Optional[str]
    image_url: Optional[str]
    video_url: Optional[str]
    url: str

async def scrape_recipes(start_url: str = "https://nishamadhulika.com/en") -> List[Recipe]:
    # Load config
    config = Config.from_env()
    
    # Define the configuration for the scraping pipeline
    graph_config = {
        "llm": {
            "model": "openai/gpt-4o-mini",
            "max_tokens": 8192,
            "api_key": config.openai_token,
        },
        "verbose": True,
        "headless": True,
        "max_nodes": 50,
        "debug": True
    }

    # Create a prompt that clearly describes what we want to extract
    extraction_prompt = """
    Analyze this webpage and determine if it's a recipe page. If it is a recipe page, extract the following information:
    - Recipe name
    - Cooking/preparation time
    - Main recipe image URL
    - YouTube video URL (if available)
    
    If this is not a recipe page, return null.
    Format the output as a JSON object with these fields.
    """

    # Create the SmartScraperMultiGraph instance
    scraper = SmartScraperMultiGraph(
        prompt=extraction_prompt,
        source=start_url,
        config=graph_config
    )

    # Run the scraper
    results = await scraper.run()
    
    recipes = []
    for result in results:
        try:
            # Parse the LLM output
            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result
                
            # Skip if not a recipe page or missing required data
            if not data or 'recipe_name' not in data:
                continue
                
            recipe = Recipe(
                name=data.get('recipe_name'),
                cooking_time=data.get('cooking_time'),
                image_url=data.get('image_url'),
                video_url=data.get('video_url'),
                url=data.get('url', '')
            )
            recipes.append(recipe)
            
        except Exception as e:
            print(f"Error processing result: {e}")
            continue
            
    return recipes

if __name__ == "__main__":
    # Run the scraper
    recipes = asyncio.run(scrape_recipes())
    
    # Print results
    for recipe in recipes:
        print("\n=== Recipe ===")
        print(f"Name: {recipe.name}")
        print(f"Cooking Time: {recipe.cooking_time}")
        print(f"Image URL: {recipe.image_url}")
        print(f"Video URL: {recipe.video_url}")
        print(f"Page URL: {recipe.url}") 