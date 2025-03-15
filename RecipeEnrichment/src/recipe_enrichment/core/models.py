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

class Recipe(BaseModel):
    """Model for the complete recipe data."""
    url: Optional[str] = None
    title: str
    summary: Optional[str] = None
    text: str  # Full recipe text
    ingredients: List[str] = []
    instructions: List[str] = []
    publish_date: Optional[datetime] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    meta_description: Optional[str] = None
    image: Optional[str] = None
    enrichment: Optional[RecipeEnrichment] = None

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

class EnrichmentPrompt(BaseModel):
    """Model for the prompt to be sent to the LLM."""
    system_message: str = """You are a culinary expert with deep knowledge of Indian cuisine. 
    Your task is to analyze recipes and provide enrichment data in valid JSON format.
    You must ONLY respond with a JSON object that matches the RecipeEnrichment model structure.
    
    IMPORTANT RULES:
    1. DO NOT modify the ingredients or instructions. Use them exactly as provided in the input.
    2. Generate an enticing, concise summary that accurately describes the dish based on the provided information.
    3. Do not include any explanations or text outside the JSON object.
    4. Ensure all numbers are integers and boolean values are true/false (lowercase).
    
    For scores, use these descriptive values:
    - Healthiness: "Very Healthy", "Healthy", "Moderate", "Unhealthy", "Very Unhealthy"
    - Ease of Cooking: "Very Easy", "Easy", "Moderate", "Difficult", "Very Difficult"
    - Ingredient Availability: "Very High", "High", "Moderate", "Low", "Very Low"
    
    Example format:
    {
        "title": "Traditional South Indian Idli",
        "generated_summary": "A delightful South Indian breakfast classic featuring soft, steamed rice cakes with a light, airy texture. Perfect for a healthy start to your day, served with traditional coconut chutney.",
        "ingredients": [
            "2 cups idli rice",
            "1 cup urad dal",
            "1 teaspoon fenugreek seeds",
            "Salt to taste"
        ],
        "instructions": [
            "Soak rice and dal separately for 4-6 hours",
            "Grind to smooth batter",
            "Ferment for 8 hours",
            "Steam in idli molds for 10 minutes"
        ],
        "healthiness_score": "Healthy",
        "ease_of_cooking_score": "Easy",
        "indian_ingredient_availability_score": "Very High",
        "prep_time_minutes": 30,
        "prep_time_breakdown": {
            "vegetable_chopping": 15,
            "spice_measuring": 5,
            "mixing_ingredients": 10
        },
        "prep_notes": "Ensure ingredients are at room temperature",
        "total_cooking_time_minutes": 45,
        "cooking_time_breakdown": {
            "initial_heating": 5,
            "sauteing_vegetables": 10,
            "simmering": 25,
            "final_garnishing": 5
        },
        "soaking_required": false,
        "soaking_time_minutes": null,
        "protein_level": "Medium",
        "meal_type_suitability": ["Breakfast", "Snack"],
        "dietary_restrictions": ["Vegetarian"],
        "categories": {
            "meal_type": ["Breakfast"],
            "dish_type": ["Snack"],
            "cooking_method": ["Steaming"],
            "region": ["South Indian"]
        }
    }"""
    
    user_message_template: str = """Analyze this recipe and respond ONLY with a JSON object containing the enrichment data.
    Do not include any other text or explanations.
    
    IMPORTANT: Use the ingredients and instructions EXACTLY as provided. Do not modify, clean, or rewrite them.
    
    Title: {title}
    Summary: {summary}
    Keywords: {keywords}
    Tags: {tags}
    Categories: {categories}
    
    Full Recipe Text:
    {text}
    
    Ingredients:
    {ingredients}
    
    Instructions:
    {instructions}
    
    Required JSON fields:
    - title (string): Original recipe title
    - generated_summary (string): Write an enticing, concise description (2-3 sentences) that makes the dish appealing
    - ingredients (array of strings): Use EXACTLY as provided in the input
    - instructions (array of strings): Use EXACTLY as provided in the input
    - healthiness_score (string): Must be one of: "Very Healthy", "Healthy", "Moderate", "Unhealthy", "Very Unhealthy"
    - ease_of_cooking_score (string): Must be one of: "Very Easy", "Easy", "Moderate", "Difficult", "Very Difficult"
    - indian_ingredient_availability_score (string): Must be one of: "Very High", "High", "Moderate", "Low", "Very Low"
    - prep_time_minutes (integer): Total preparation time
    - prep_time_breakdown (object): Detailed breakdown of preparation steps and their times in minutes
    - prep_notes (string or null): Any special preparation notes or tips
    - total_cooking_time_minutes (integer): Total time needed for cooking
    - cooking_time_breakdown (object): Detailed breakdown of cooking steps and their times in minutes
    - soaking_required (boolean): Whether any ingredients need soaking
    - soaking_time_minutes (integer or null): Time needed for soaking (if applicable)
    - protein_level (string): Must be exactly "High", "Medium", or "Low"
    - meal_type_suitability (array of strings): List suitable meal types
    - dietary_restrictions (array of strings): List applicable dietary restrictions
    - categories (object): Dictionary with:
        - meal_type (array of strings): List of suitable meal types
        - dish_type (array of strings): List of dish types
        - cooking_method (array of strings): List of cooking methods used
        - region (array of strings): List of Indian regions this recipe relates to
        
    Important Notes:
    1. DO NOT modify ingredients or instructions - use them exactly as provided
    2. For time calculations, analyze each step carefully and provide realistic estimates
    3. Break down preparation time into specific tasks (e.g., chopping, mixing)
    4. Break down cooking time into specific steps (e.g., heating oil, sautéing, simmering)
    5. Base your estimates on standard cooking practices and typical ingredient quantities""" 