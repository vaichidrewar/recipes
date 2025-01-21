from scrapegraphai.graphs import SmartScraperGraph
from dataclasses import dataclass
from typing import Optional, List
import json
from config import Config

@dataclass
class Recipe:
    name: str
    cooking_time: Optional[str]
    image_url: Optional[str]
    video_url: Optional[str]
    url: str

def scrape_recipes(start_url: str = "https://nishamadhulika.com/en") -> List[Recipe]:
    # Load config
    config = Config.from_env()
    
    # Define the configuration for the scraping pipeline
    graph_config = {
        "llm": {
            "model": "openai/gpt-4o-mini",            
            "api_key": config.openai_token,
        },
        "verbose": True,
        "headless": True,
        "debug": True
    }

    # Create a prompt that clearly describes what we want to extract
    extraction_prompt = """
    Analyze this webpage and determine if it's a recipe page. If it is a recipe page, extract the following information:
    - Recipe name
    - Cooking/preparation time
    - Main recipe image URL
    - YouTube video URL (if available)
    
    Return the data as a JSON object with these exact fields: recipe_name, cooking_time, image_url, video_url.
    If this is not a recipe page, return null.
    """

    # Create the SmartScraperGraph instance
    scraper = SmartScraperGraph(
        prompt=extraction_prompt,
        source=start_url,
        config=graph_config
    )

    # Run the scraper
    results = scraper.run()
    
    recipes = []
    try:
        # Parse the LLM output
        if isinstance(results, str):
            data = json.loads(results)
        else:
            data = results
            
        if data and 'recipe_name' in data:
            recipe = Recipe(
                name=data.get('recipe_name'),
                cooking_time=data.get('cooking_time'),
                image_url=data.get('image_url'),
                video_url=data.get('video_url'),
                url=start_url
            )
            recipes.append(recipe)
            
    except Exception as e:
        print(f"Error processing result: {e}")
            
    return recipes

if __name__ == "__main__":
    recipes = scrape_recipes()
    
    # Print results
    for recipe in recipes:
        print("\n=== Recipe ===")
        print(f"Name: {recipe.name}")
        print(f"Cooking Time: {recipe.cooking_time}")
        print(f"Image URL: {recipe.image_url}")
        print(f"Video URL: {recipe.video_url}")
        print(f"Page URL: {recipe.url}") 