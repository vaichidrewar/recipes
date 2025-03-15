import pytest
from pathlib import Path
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.recipe_enrichment.core.models import Recipe, RecipeEnrichment
from src.recipe_enrichment.core.enricher import RecipeEnricher

@pytest.fixture
def sample_recipe():
    return Recipe(
        title="Test Recipe",
        text="""
        This is a test recipe.
        
        Ingredients:
        ingredient1
        ingredient2
        
        How to make:
        step1
        step2
        """,
        ingredients=["ingredient1", "ingredient2"],
        instructions=["step1", "step2"]
    )

@pytest.fixture
def enricher():
    return RecipeEnricher()

@pytest.fixture
def mock_openai_response():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "healthiness_score": 4,
        "ease_of_cooking_score": 3,
        "indian_ingredient_availability_score": 5,
        "prep_time_minutes": 30,
        "prep_notes": "Test notes",
        "total_cooking_time_minutes": 45,
        "soaking_required": False,
        "protein_level": "Medium",
        "meal_type_suitability": ["Lunch", "Dinner"],
        "dietary_restrictions": ["Vegetarian"],
        "categories": {
            "meal_type": ["Lunch"],
            "dish_type": ["Curry"],
            "cooking_method": ["Stir-Fry"],
            "region": ["North Indian"]
        }
    })
    return mock_response

def test_recipe_extraction():
    """Test that ingredients and instructions are properly extracted from text."""
    # Create a recipe with only text
    recipe = Recipe(
        title="Test Recipe",
        text="""
        This is a test recipe.
        
        Ingredients:
        - flour 1 cup
        - water 1 cup
        
        How to make:
        1. Mix flour and water
        2. Cook the mixture
        """
    )
    
    assert len(recipe.ingredients) > 0, "Ingredients should be extracted from text"
    assert len(recipe.instructions) > 0, "Instructions should be extracted from text"
    assert any("flour" in ing.lower() for ing in recipe.ingredients), "Ingredients should contain flour"
    assert any("mix" in inst.lower() for inst in recipe.instructions), "Instructions should contain mixing step"

@pytest.mark.asyncio
async def test_enrich_single_recipe(enricher, sample_recipe, mock_openai_response):
    """Test recipe enrichment with mocked OpenAI API."""
    mock_completion = AsyncMock()
    mock_completion.return_value = mock_openai_response
    
    with patch('openai.resources.chat.completions.Completions.create', mock_completion):
        enriched_recipe = await enricher._enrich_single_recipe(sample_recipe)
        
        assert enriched_recipe.enrichment is not None
        assert enriched_recipe.enrichment.healthiness_score == 4
        assert enriched_recipe.enrichment.ease_of_cooking_score == 3
        assert isinstance(enriched_recipe.enrichment.meal_type_suitability, list)

def test_save_enriched_recipes(enricher, sample_recipe, tmp_path):
    """Test saving enriched recipes to file."""
    # Create a sample enrichment
    sample_recipe.enrichment = RecipeEnrichment(
        healthiness_score=4,
        ease_of_cooking_score=3,
        indian_ingredient_availability_score=5,
        prep_time_minutes=30,
        total_cooking_time_minutes=45,
        soaking_required=False,
        protein_level="Medium",
        meal_type_suitability=["Lunch", "Dinner"],
        dietary_restrictions=["Vegetarian"],
        categories={
            "meal_type": ["Lunch"],
            "dish_type": ["Curry"],
            "cooking_method": ["Stir-Fry"],
            "region": ["North Indian"]
        }
    )
    
    # Save the recipe
    output_file = tmp_path / "test_output.json"
    enricher.save_enriched_recipes([sample_recipe], output_file)
    
    # Verify the saved file
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    assert len(saved_data) == 1
    assert saved_data[0]["title"] == "Test Recipe"
    assert saved_data[0]["enrichment"]["healthiness_score"] == 4 