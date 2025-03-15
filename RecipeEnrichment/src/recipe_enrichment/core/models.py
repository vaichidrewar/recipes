from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator
from datetime import datetime

class RecipeEnrichment(BaseModel):
    """Model for enriched recipe data."""
    title: str = Field(..., description="Original recipe title")
    generated_summary: str = Field(..., description="An enticing, concise description of the dish for recipe cards")
    ingredients: List[str] = Field(..., description="Clean list of ingredients from the input, without recipe name or other text")
    instructions: List[str] = Field(..., description="Clean list of cooking steps from the input, without recipe name or other text")
    healthiness_score: str = Field(..., pattern="^(Very Healthy|Healthy|Moderate|Unhealthy|Very Unhealthy)$")
    ease_of_cooking_score: str = Field(..., pattern="^(Very Easy|Easy|Moderate|Difficult|Very Difficult)$")
    indian_ingredient_availability_score: str = Field(..., pattern="^(Very High|High|Moderate|Low|Very Low)$")
    prep_time_minutes: int = Field(..., ge=0)
    prep_time_breakdown: dict = Field(..., description="Detailed breakdown of preparation steps and their estimated times")
    prep_notes: Optional[str] = None
    total_cooking_time_minutes: int = Field(..., ge=0)
    cooking_time_breakdown: dict = Field(..., description="Detailed breakdown of cooking steps and their estimated times")
    soaking_required: bool = False
    soaking_time_minutes: Optional[int] = Field(None, ge=0)
    protein_level: str = Field(..., pattern="^(High|Medium|Low)$")
    meal_type_suitability: List[str]
    dietary_restrictions: List[str]
    categories: dict = Field(..., description="Dictionary containing meal type, dish type, cooking method, and region")
    original_categories: List[str] = Field([], description="Original list of categories from the input recipe")
    
    # Meal prep guidance
    meal_prep_guidance: Optional[dict] = Field(None, description="Guidance for meal prep that can be done ahead of time, including components that can be prepared in advance and storage instructions")
    
    # URL fields
    recipe_url: Optional[str] = Field(None, description="URL of the original recipe page")
    image_url: Optional[str] = Field(None, description="URL of the main recipe image")
    video_url: Optional[str] = Field(None, description="URL of the recipe video if available")
    additional_images: Optional[List[str]] = Field(None, description="List of additional image URLs related to the recipe")

class Recipe(BaseModel):
    """Model for the complete recipe data."""
    title: str
    summary: Optional[str] = None
    text: Optional[str] = None
    ingredients: List[str] = []
    instructions: List[str] = []
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    enrichment: Optional[RecipeEnrichment] = None
    
    # URL fields
    url: Optional[str] = None
    top_image: Optional[str] = None
    meta_img: Optional[str] = None
    images: Optional[List[str]] = None
    movies: Optional[List[str]] = None

    @staticmethod
    def _extract_section(text: str, section_name: str) -> List[str]:
        """Extract a section from recipe text."""
        try:
            # Find the section
            start_idx = text.find(section_name)
            if start_idx == -1:
                return []
            
            # Move past the section name and any following characters
            content_start = start_idx + len(section_name)
            while content_start < len(text) and (text[content_start].isspace() or text[content_start] in ':-'):
                content_start += 1
            
            # Find the next section or end of text
            next_sections = ["How to make", "Suggestion", "For", "Time", "Video", "Tags", "Categories"]
            end_indices = []
            for section in next_sections:
                idx = text.find(section, content_start)
                if idx != -1:
                    end_indices.append(idx)
            
            end_idx = min(end_indices) if end_indices else len(text)
            
            # Extract the section content
            section_text = text[content_start:end_idx].strip()
            
            # Split into lines and clean up
            items = []
            for line in section_text.split("\n"):
                line = line.strip()
                if line and not line.isspace():
                    # Remove bullet points, numbers, or dashes if present
                    if line.startswith(("•", "-", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "0.")):
                        line = line.split(".", 1)[-1] if "." in line else line[1:]
                    line = line.strip()
                    if line:  # Only add non-empty lines
                        items.append(line)
            
            return items
        except Exception:
            return []

    @model_validator(mode='after')
    def extract_ingredients_and_instructions(self) -> 'Recipe':
        """Extract ingredients and instructions from recipe text if not provided."""
        if not self.ingredients:
            self.ingredients = self._extract_section(self.text, "Ingredients")
        
        if not self.instructions:
            instructions_text = self._extract_section(self.text, "How to make")
            if not instructions_text and "Instructions" in self.text:
                instructions_text = self._extract_section(self.text, "Instructions")
            self.instructions = instructions_text

        return self

class EnrichmentPrompt:
    """Prompt templates for recipe enrichment."""
    
    def __init__(self):
        self.system_message = """You are a culinary expert AI assistant specializing in recipe analysis and enrichment. Your task is to analyze recipe data and extract structured information.

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

        self.user_message_template = """Please analyze and enrich the following recipe:

TITLE: {title}

SUMMARY: {summary}

KEYWORDS: {keywords}

TAGS: {tags}

CATEGORIES: {categories}

FULL TEXT: {text}

INGREDIENTS:
{ingredients}

INSTRUCTIONS:
{instructions}

WARNING: Use the ingredients and instructions EXACTLY as provided above. Do not modify, clean, or rewrite them.

Please extract and structure this recipe data into a comprehensive JSON format with the following fields:
- title: The recipe title
- generated_summary: Generate a creative, enticing, and **unique** summary of the recipe (2-3 sentences maximum) that will make the reader want to cook this recipe. **Avoid starting with common and predictable phrases like "Craving a...", "Looking for a...", "This recipe is...", "Imagine biting into...", or similar generic openings.** Aim for variety in tone and focus. Highlight a key appealing aspect of the dish, such as its flavor profile, ease of preparation, health benefits, or unique ingredients.
- ingredients: Array of ingredients (preserve original wording and ordering)
- instructions: Array of cooking steps (preserve original wording and ordering)
- healthiness_score: One of ["Very Healthy", "Healthy", "Moderate", "Unhealthy", "Very Unhealthy"]
- ease_of_cooking_score: One of ["Very Easy", "Easy", "Moderate", "Difficult", "Very Difficult"]
- indian_ingredient_availability_score: One of ["Very High", "High", "Moderate", "Low", "Very Low"]
- protein_level: One of ["High", "Medium", "Low"]
- prep_time_minutes: Total preparation time in minutes
- prep_time_breakdown: Object with preparation steps and their times
- prep_notes: Any special preparation notes (e.g., tasks that can be done in parallel)
- total_cooking_time_minutes: Total cooking time in minutes
- cooking_time_breakdown: Object with cooking steps and their times
- soaking_required: Boolean indicating if soaking is needed
- soaking_time_minutes: Soaking time in minutes (if applicable)
- meal_type_suitability: Array of suitable meal types
- dietary_restrictions: Array of dietary restrictions this recipe accommodates
- categories: Object with the following structure:
  * meal_type: Array of meal types (e.g., ["Curry", "Main Course"])
  * dish_type: Array of dish types (e.g., ["Vegetable", "Soup", "Stew"])
  * cooking_method: Array of cooking methods (e.g., ["Pressure Cooking", "Sautéing", "Simmering"])
  * region: Array of regional cuisines (e.g., ["Indian", "North Indian"])
  * cuisine_type: Array of specific cuisine styles (e.g., ["Punjabi", "Mughlai", "Street Food"])
  * main_ingredients: Array of key ingredients that define the dish (e.g., ["Lentils", "Spinach", "Kidney Beans"])
  * special_occasion: Array of occasions this dish is suitable for (e.g., ["Festival", "Everyday", "Party"])
- meal_prep_guidance: Goal here is to provide guidance for preparation ahead of time to save cooking time on a busy day, not too much prep ahead of time either to avoid getting overwhelmed on weekend, balance of prep before and at the time of recipe making. This will be object containing:
 * components_to_prep: Array of recipe components that can be prepared ahead of time
  * prep_instructions: Object with specific instructions for each component
  * storage_info: Object with storage methods and estimated shelf life for each component
  * final_assembly: Instructions for final assembly after meal prep
  * time_saving_tips: Tips to save time during weekly meal prep

The URLs from the original recipe will be automatically included in the enriched data.

Respond ONLY with the JSON object.""" 