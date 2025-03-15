import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import random
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
import re
import logging

from .config.settings import config, ModelType
from .core.models import Recipe
from .core.enricher import create_enricher

console = Console()

def load_sample_recipes(file_path: Path, num_recipes: int = 1) -> List[Recipe]:
    """Load sample recipes from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_recipes = json.load(f)
        
        # Shuffle recipes to get random ones
        random.shuffle(all_recipes)
        
        recipes = []
        for recipe_data in all_recipes:
            # Skip recipes without required fields
            if not recipe_data.get('title'):
                continue
            
            # Extract ingredients and instructions from text if they're not provided
            ingredients = recipe_data.get('ingredients', [])
            instructions = recipe_data.get('instructions', [])
            
            # If ingredients are missing, try to extract from text
            if not ingredients and recipe_data.get('text'):
                text = recipe_data.get('text', '')
                
                # Look for ingredient section markers in the text
                ingredient_markers = [
                    "Essential ingredients required", 
                    "Ingredients required", 
                    "Ingredients:", 
                    "Ingredients needed",
                    "You will need"
                ]
                
                for marker in ingredient_markers:
                    if marker in text:
                        # Find the start of ingredients section
                        start_idx = text.find(marker) + len(marker)
                        
                        # Find the end of ingredients section (next section or recipe name)
                        end_markers = ["Recipe:", "Instructions:", "Method:", "Preparation:", "Directions:"]
                        end_indices = [text.find(end_marker, start_idx) for end_marker in end_markers if text.find(end_marker, start_idx) > 0]
                        
                        # If no explicit end marker, look for a paragraph break
                        if not end_indices:
                            paragraph_breaks = [m.start() for m in re.finditer(r'\n\n', text[start_idx:])]
                            if paragraph_breaks:
                                end_idx = start_idx + paragraph_breaks[0]
                            else:
                                end_idx = len(text)
                        else:
                            end_idx = min(end_indices)
                        
                        # Extract the ingredients text
                        ingredients_text = text[start_idx:end_idx].strip()
                        
                        # Split by newlines and clean up
                        extracted_ingredients = [line.strip() for line in ingredients_text.split('\n') if line.strip()]
                        
                        # Filter out lines that don't look like ingredients
                        ingredients = [item for item in extracted_ingredients if re.search(r'[-:]|\d+|cup|tsp|tbsp|gram', item)]
                        
                        logging.info(f"Extracted {len(ingredients)} ingredients from text for recipe {recipe_data['title']}")
                        break
            
            # If instructions are missing, try to extract from text
            if not instructions and recipe_data.get('text'):
                text = recipe_data.get('text', '')
                
                # Look for recipe/instructions section markers
                instruction_markers = [
                    "Recipe:", 
                    "Instructions:", 
                    "Method:", 
                    "Preparation:", 
                    "Directions:",
                    "How to prepare",
                    "How to make"
                ]
                
                # If the recipe name is in the text, it might mark the start of instructions
                recipe_name_markers = []
                if recipe_data.get('title'):
                    title_parts = recipe_data['title'].split()
                    if len(title_parts) > 2:
                        recipe_name_markers.append(title_parts[0] + " " + title_parts[1])
                    recipe_name_markers.append(recipe_data['title'].split('Recipe')[0].strip() + " Recipe")
                
                all_markers = instruction_markers + recipe_name_markers
                
                for marker in all_markers:
                    if marker in text:
                        # Find the start of instructions section
                        start_idx = text.find(marker) + len(marker)
                        
                        # Find the end of instructions section (next section like tags, categories)
                        end_markers = ["Tags", "Categories", "Notes:", "Tips:"]
                        end_indices = [text.find(end_marker, start_idx) for end_marker in end_markers if text.find(end_marker, start_idx) > 0]
                        
                        if end_indices:
                            end_idx = min([idx for idx in end_indices if idx > 0])
                        else:
                            end_idx = len(text)
                        
                        # Extract the instructions text
                        instructions_text = text[start_idx:end_idx].strip()
                        
                        # Split by paragraphs or numbered steps
                        if re.search(r'\d+\.\s', instructions_text):
                            # If numbered steps are present
                            extracted_instructions = re.split(r'\d+\.\s', instructions_text)
                            # Remove empty strings and clean up
                            extracted_instructions = [step.strip() for step in extracted_instructions if step.strip()]
                        else:
                            # Split by paragraphs
                            extracted_instructions = [p.strip() for p in instructions_text.split('\n\n') if p.strip()]
                            
                            # If paragraphs are too long, try splitting by newlines
                            if extracted_instructions and all(len(p) > 200 for p in extracted_instructions):
                                extracted_instructions = [p.strip() for p in instructions_text.split('\n') if p.strip()]
                        
                        # Filter out very short lines or lines that look like headings
                        instructions = [step for step in extracted_instructions if len(step) > 15 and not step.isupper()]
                        
                        logging.info(f"Extracted {len(instructions)} instructions from text for recipe {recipe_data['title']}")
                        break
            
            # If we still don't have ingredients or instructions, try a more aggressive approach
            if not ingredients and recipe_data.get('text'):
                # Look for lines that look like ingredients (contain measurements)
                text_lines = recipe_data.get('text', '').split('\n')
                potential_ingredients = []
                
                for line in text_lines:
                    line = line.strip()
                    # Check if line contains measurements or common ingredient indicators
                    if re.search(r'\d+\s*(cup|tbsp|tsp|g|gram|ml|oz|pound|lb|kg)', line, re.IGNORECASE):
                        potential_ingredients.append(line)
                
                if potential_ingredients:
                    ingredients = potential_ingredients
                    logging.info(f"Extracted {len(ingredients)} ingredients using pattern matching for recipe {recipe_data['title']}")
            
            # If we still don't have instructions, use paragraphs from the text
            if not instructions and recipe_data.get('text'):
                text = recipe_data.get('text', '')
                # Skip the first paragraph (usually introduction)
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()][1:]
                
                # Filter out short paragraphs and those that don't look like instructions
                potential_instructions = [p for p in paragraphs if len(p) > 30 and not p.startswith('Tag') and not p.startswith('Categor')]
                
                if potential_instructions:
                    instructions = potential_instructions
                    logging.info(f"Extracted {len(instructions)} instructions using paragraphs for recipe {recipe_data['title']}")
            
            # If we still don't have ingredients or instructions, skip this recipe
            if not ingredients or not instructions:
                logging.warning(f"Skipping recipe {recipe_data.get('title')} due to missing ingredients or instructions")
                continue
            
            # Create Recipe object
            recipe = Recipe(
                title=recipe_data.get('title', ''),
                summary=recipe_data.get('summary', '') or recipe_data.get('meta_description', ''),
                text=recipe_data.get('text', ''),
                ingredients=ingredients,
                instructions=instructions,
                keywords=recipe_data.get('keywords', []),
                tags=recipe_data.get('tags', []),
                categories=recipe_data.get('meta_keywords', []),
                url=recipe_data.get('url', ''),
                top_image=recipe_data.get('top_image', ''),
                meta_img=recipe_data.get('meta_img', ''),
                images=recipe_data.get('images', []),
                movies=recipe_data.get('movies', [])
            )
            
            recipes.append(recipe)
            
            if len(recipes) >= num_recipes:
                break
        
        # If we didn't get enough recipes, try to load more
        if len(recipes) < num_recipes:
            logging.info(f"Only loaded {len(recipes)} recipes, trying to load {num_recipes - len(recipes)} more...")
            remaining_recipes = load_sample_recipes(file_path, num_recipes - len(recipes))
            recipes.extend(remaining_recipes)
        
        return recipes
    except Exception as e:
        logging.error(f"Error loading recipes: {str(e)}")
        return []

def print_recipe_comparison(recipe: Recipe):
    """Print a before/after comparison of a recipe."""
    console.print("\n" + "="*120)
    console.print(Panel.fit(f"[bold blue]Recipe: {recipe.title}[/bold blue]"))
    
    # Print original recipe data
    console.print("\n[bold yellow]Original Recipe Data:[/bold yellow]")
    console.print(Panel(
        "\n".join([
            f"[bold cyan]Title:[/bold cyan] {recipe.title}",
            f"\n[bold cyan]Summary:[/bold cyan]\n{recipe.summary or 'Not provided'}",
            f"\n[bold cyan]Keywords:[/bold cyan]\n{', '.join(recipe.keywords) if recipe.keywords else 'Not provided'}",
            f"\n[bold cyan]Tags:[/bold cyan]\n{', '.join(recipe.tags) if recipe.tags else 'Not provided'}",
            f"\n[bold cyan]Categories:[/bold cyan]\n{', '.join(recipe.categories) if recipe.categories else 'Not provided'}",
            f"\n[bold cyan]URL:[/bold cyan]\n{recipe.url if hasattr(recipe, 'url') else 'Not provided'}",
            f"\n[bold cyan]Main Image:[/bold cyan]\n{recipe.top_image if hasattr(recipe, 'top_image') else (recipe.meta_img if hasattr(recipe, 'meta_img') else 'Not provided')}",
            f"\n[bold cyan]Video:[/bold cyan]\n{recipe.movies[0] if hasattr(recipe, 'movies') and recipe.movies else 'Not provided'}",
            f"\n[bold cyan]Full Recipe Text:[/bold cyan]\n{recipe.text}",
            f"\n[bold cyan]Ingredients ({len(recipe.ingredients)}):[/bold cyan]",
            *[f"  {i+1}. {ing}" for i, ing in enumerate(recipe.ingredients)],
            f"\n[bold cyan]Instructions ({len(recipe.instructions)}):[/bold cyan]",
            *[f"  {i+1}. {inst}" for i, inst in enumerate(recipe.instructions)]
        ]),
        title="[bold yellow]Input Data[/bold yellow]",
        expand=True,
        width=115  # Set a fixed width for better formatting
    ))
    
    # Print enrichment data
    if recipe.enrichment:
        console.print("\n[bold green]Enrichment Data:[/bold green]")
        enrichment_dict = recipe.enrichment.model_dump()
        
        # Format the enrichment data for better readability
        formatted_enrichment = {
            "Basic Information": {
                "Title": enrichment_dict["title"],
                "Generated Summary": enrichment_dict["generated_summary"]
            },
            "Recipe Details": {
                "Ingredients": enrichment_dict["ingredients"],
                "Instructions": enrichment_dict["instructions"]
            },
            "URLs": {
                "Recipe URL": enrichment_dict.get("recipe_url", "Not provided"),
                "Main Image": enrichment_dict.get("image_url", "Not provided"),
                "Video": enrichment_dict.get("video_url", "Not provided"),
                "Additional Images Count": len(enrichment_dict.get("additional_images", [])) if enrichment_dict.get("additional_images") else 0
            },
            "Meal Prep Guidance": enrichment_dict.get("meal_prep_guidance", "Not provided"),
            "Scores": {
                "Healthiness": enrichment_dict["healthiness_score"],
                "Ease of Cooking": enrichment_dict["ease_of_cooking_score"],
                "Indian Ingredient Availability": enrichment_dict["indian_ingredient_availability_score"],
                "Protein Level": enrichment_dict["protein_level"]
            },
            "Time Information": {
                "Preparation Time": f"{enrichment_dict['prep_time_minutes']} minutes",
                "Preparation Breakdown": enrichment_dict["prep_time_breakdown"],
                "Cooking Time": f"{enrichment_dict['total_cooking_time_minutes']} minutes",
                "Cooking Breakdown": enrichment_dict["cooking_time_breakdown"],
                "Soaking Required": enrichment_dict["soaking_required"],
                "Soaking Time": f"{enrichment_dict['soaking_time_minutes']} minutes" if enrichment_dict["soaking_time_minutes"] else "Not required"
            },
            "Notes": enrichment_dict["prep_notes"] or "No special notes",
            "Categories": {
                "Meal Types": enrichment_dict["meal_type_suitability"],
                "Dietary Restrictions": enrichment_dict["dietary_restrictions"],
                "Structured Categories": enrichment_dict["categories"],
                "Original Categories": enrichment_dict.get("original_categories", [])
            }
        }
        
        # Convert to JSON string with proper indentation and ensure_ascii=False for Unicode
        json_str = json.dumps(formatted_enrichment, indent=2, ensure_ascii=False)
        
        # Create a panel with the formatted JSON
        console.print(Panel(
            json_str,
            title="[bold green]Enriched Recipe Data[/bold green]",
            expand=True,
            width=115,  # Set a fixed width for better formatting
            border_style="green"
        ))
    
    console.print("="*120 + "\n")

async def main():
    """Run enrichment on a sample of recipes."""
    try:
        # Cache management options
        console.print("[yellow]Recipe Enrichment Options:[/yellow]")
        console.print("1. Process recipes")
        console.print("2. Clear cache")
        console.print("3. View cache statistics")
        option_choice = input().strip()
        
        # Initialize cache
        from .core.cache import RecipeCache
        cache = RecipeCache()
        
        if option_choice == "2":
            # Clear cache
            if cache.clear():
                console.print("[green]Cache cleared successfully![/green]")
            else:
                console.print("[red]Failed to clear cache.[/red]")
            return
        elif option_choice == "3":
            # View cache statistics
            cache_dir = cache.cache_dir
            cache_files = list(cache_dir.glob("*.json"))
            
            if not cache_files:
                console.print("[yellow]Cache is empty.[/yellow]")
                return
            
            # Count files by model type
            model_counts = {}
            for file in cache_files:
                model_type = file.stem.split("_")[-1]
                model_counts[model_type] = model_counts.get(model_type, 0) + 1
            
            console.print(f"[green]Cache contains {len(cache_files)} recipes:[/green]")
            for model, count in model_counts.items():
                console.print(f"  - {model}: {count} recipes")
            
            # Calculate cache size
            total_size = sum(file.stat().st_size for file in cache_files)
            console.print(f"[green]Total cache size: {total_size / 1024:.2f} KB[/green]")
            return
        elif option_choice != "1":
            console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")
            return
        
        # Select model
        console.print("[yellow]Which model would you like to use?[/yellow]")
        console.print("1. GPT-4")
        console.print("2. Claude")
        console.print("3. Gemini")
        model_choice = input().strip()
        
        if model_choice == "1":
            config.MODEL_TYPE = ModelType.GPT4
            config.MODEL_NAME = config.MODEL_TYPE.value
            if not config.openai_token:
                console.print("[red]Error: OpenAI token not found. Please set the OPENAI_TOKEN environment variable.[/red]")
                return
        elif model_choice == "2":
            config.MODEL_TYPE = ModelType.CLAUDE
            config.MODEL_NAME = config.MODEL_TYPE.value
            if not config.anthropic_token:
                console.print("[red]Error: Anthropic token not found. Please set the ANTHROPIC_API_KEY environment variable.[/red]")
                return
        elif model_choice == "3":
            config.MODEL_TYPE = ModelType.GEMINI
            config.MODEL_NAME = config.MODEL_TYPE.value
            if not config.google_token:
                console.print("[red]Error: Gemini API token not found. Please set the GEMINI_API_KEY environment variable.[/red]")
                return
        else:
            console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")
            return
        
        console.print(f"[green]Using model: {config.MODEL_NAME}[/green]")
        
        # Get sample size from user
        console.print("\n[yellow]How many recipes would you like to process? (1-5)[/yellow]")
        sample_size = int(input().strip())
        if not 1 <= sample_size <= 5:
            console.print("[red]Please enter a number between 1 and 5[/red]")
            return
        
        # Load sample recipes
        console.print(f"\n[green]Loading {sample_size} random recipes from {config.INPUT_FILE}...[/green]")
        recipes = load_sample_recipes(config.INPUT_FILE, sample_size)
        console.print(f"[green]Loaded {len(recipes)} recipes[/green]")
        
        # Initialize enricher based on selected model
        enricher = create_enricher()
        
        # Process recipes
        enriched_recipes = []
        for recipe in recipes:
            console.print(f"\n[yellow]Processing recipe: {recipe.title}[/yellow]")
            try:
                enriched_recipe = await enricher._enrich_single_recipe(recipe)
                enriched_recipes.append(enriched_recipe)
                print_recipe_comparison(enriched_recipe)
            except Exception as e:
                console.print(f"[red]Error enriching recipe {recipe.title}: {str(e)}[/red]")
                continue
        
        # Save enriched recipes to disk
        if enriched_recipes:
            # Create output directory if it doesn't exist
            output_dir = Path(config.OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate output filename with timestamp and model type
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"enriched_recipes_{config.MODEL_TYPE.name.lower()}_{timestamp}.json"
            
            # Save only the enrichment data to file (not the full recipe objects)
            enrichment_data = []
            for recipe in enriched_recipes:
                if recipe.enrichment:
                    # Add the recipe title to the enrichment data for reference
                    enrichment_json = recipe.enrichment.model_dump()
                    enrichment_data.append(enrichment_json)
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(
                    enrichment_data,
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            console.print(f"[green]Saved {len(enrichment_data)} enriched recipes to {output_file}[/green]")
        
        console.print("[green]Sample processing complete![/green]")
        
    except Exception as e:
        console.print(f"[red]Error during sample processing: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 