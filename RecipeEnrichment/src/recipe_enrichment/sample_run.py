import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import random
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON

from .config.settings import config
from .core.models import Recipe
from .core.enricher import RecipeEnricher

console = Console()

async def load_sample_recipes(file_path: Path, sample_size: int = 1) -> List[Recipe]:
    """Load a random sample of recipes from the JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Take a random sample
        if isinstance(data, list):
            if len(data) < sample_size:
                sample_size = len(data)
            sample_data = random.sample(data, sample_size)
        else:
            sample_data = [data]
        
        recipes = []
        for recipe_data in sample_data:
            try:
                recipe = Recipe(**recipe_data)
                recipes.append(recipe)
            except Exception as e:
                console.print(f"[red]Error parsing recipe {recipe_data.get('title', 'Unknown')}: {str(e)}[/red]")
                continue
        
        return recipes
    
    except Exception as e:
        console.print(f"[red]Error loading recipes: {str(e)}[/red]")
        raise

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
                "Detailed Categories": enrichment_dict["categories"]
            }
        }
        
        # Convert to JSON string with proper indentation
        json_str = json.dumps(formatted_enrichment, indent=2)
        
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
        # Ensure OpenAI token is set
        if not config.openai_token:
            console.print("[red]Error: OpenAI token not found. Please set the OPENAI_TOKEN environment variable.[/red]")
            return
        
        # Get sample size from user
        console.print("[yellow]How many recipes would you like to process? (1-5)[/yellow]")
        sample_size = int(input().strip())
        if not 1 <= sample_size <= 5:
            console.print("[red]Please enter a number between 1 and 5[/red]")
            return
        
        # Load sample recipes
        console.print(f"\n[green]Loading {sample_size} random recipes from {config.INPUT_FILE}...[/green]")
        recipes = await load_sample_recipes(config.INPUT_FILE, sample_size)
        console.print(f"[green]Loaded {len(recipes)} recipes[/green]")
        
        # Initialize enricher
        enricher = RecipeEnricher()
        
        # Process recipes
        for recipe in recipes:
            console.print(f"\n[yellow]Processing recipe: {recipe.title}[/yellow]")
            try:
                enriched_recipe = await enricher._enrich_single_recipe(recipe)
                print_recipe_comparison(enriched_recipe)
            except Exception as e:
                console.print(f"[red]Error enriching recipe {recipe.title}: {str(e)}[/red]")
                continue
        
        console.print("[green]Sample processing complete![/green]")
        
    except Exception as e:
        console.print(f"[red]Error during sample processing: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 