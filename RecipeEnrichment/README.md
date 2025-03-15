# Recipe Data Enrichment

This project uses OpenAI's GPT API to enrich recipe data with additional metadata such as healthiness scores, cooking difficulty, and ingredient availability in India.

## Features

- Enriches recipe data with:
  - Healthiness Score (1-5)
  - Ease of Cooking Score (1-5)
  - Indian Ingredient Availability Score (1-5)
  - Preparation Time
  - Cooking Time
  - Soaking Requirements
  - Protein Level
  - Meal Type Suitability
  - Dietary Restrictions
  - Recipe Categories

## Prerequisites

- Python 3.8 or higher
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd recipe-enrichment
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Place your recipe JSON file in the project root directory (default: `recipes_1500.json`).

2. Run the enrichment script:
```bash
python -m src.recipe_enrichment
```

The enriched recipes will be saved in the `enriched_recipes` directory, with both batch files and a final combined file.

## Configuration

You can modify the following settings in `src/recipe_enrichment/config/settings.py`:

- `BATCH_SIZE`: Number of recipes to process in each batch
- `MODEL_NAME`: OpenAI model to use
- `MAX_RETRIES`: Maximum number of API call retries
- `INPUT_FILE`: Input JSON file path
- `OUTPUT_DIR`: Output directory for enriched recipes

## Error Handling

The script includes comprehensive error handling:
- API rate limiting and retry logic
- Batch processing with intermediate saves
- Detailed logging
- Input validation using Pydantic models

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License. 