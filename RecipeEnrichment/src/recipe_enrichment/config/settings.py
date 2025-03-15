from pathlib import Path
from pydantic import BaseModel
import os

class Config(BaseModel):
    """Configuration settings for the recipe enrichment project."""
    
    # API Settings
    openai_token: str = os.getenv('OPENAI_TOKEN')  # Get token directly from environment
    MODEL_NAME: str = "gpt-3.5-turbo"  # Using GPT-3.5 Turbo for cost-effective performance
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1
    
    # File Paths
    INPUT_FILE: Path = Path("recipes_1500.json")
    OUTPUT_DIR: Path = Path("enriched_recipes")
    
    # Batch Processing
    BATCH_SIZE: int = 10
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = Path("recipe_enrichment.log")

config = Config() 