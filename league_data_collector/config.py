"""Configuration settings for the League Data Collector."""
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
# Try loading from project root first, then from package directory
env_paths = [
    Path(__file__).parent.parent / '.env',  # Project root
    Path(__file__).parent / '.env'          # Package directory
]

# Load the first .env file that exists
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        break
else:
    # If no .env file was found, log a warning but continue
    import warnings
    warnings.warn(
        "No .env file found. Please create one in either the project root or the league_data_collector directory."
    )

class Settings:
    """Application settings loaded from environment variables."""
    
    # API Configuration
    RIOT_API_KEY: str = os.getenv("RIOT_API_KEY", "")
    RIOT_API_RATE_LIMIT: int = int(os.getenv("RIOT_API_RATE_LIMIT", "20"))
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{Path(__file__).parent.parent}/league_data.db"
    )
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # API Endpoints
    RIOT_API_BASE_URL = "https://{region}.api.riotgames.com"
    RIOT_API_REGIONAL_BASE_URL = "https://{region}.api.riotgames.com"
    
    # Supported Regions
    SUPPORTED_REGIONS = {
        'na': 'na1',
        'euw': 'euw1',
        'eune': 'eun1',
        'kr': 'kr',
        'br': 'br1',
        'jp': 'jp1',
        'ru': 'ru',
        'oce': 'oc1',
        'tr': 'tr1',
        'la1': 'la1',
        'la2': 'la2',
    }
    
    # Match Queue Types (add more as needed)
    QUEUE_TYPES = {
        420: 'RANKED_SOLO_5x5',
        440: 'RANKED_FLEX_SR',
        430: 'NORMAL_BLIND_PICK',
        400: 'NORMAL_DRAFT_PICK',
        450: 'ARAM',
    }

# Global settings instance
settings = Settings()

def validate_config() -> tuple[bool, list[str]]:
    """Validate the current configuration.
    
    Returns:
        tuple: (is_valid, error_messages)
    """
    errors = []
    
    if not settings.RIOT_API_KEY:
        errors.append("RIOT_API_KEY is not set in .env file")
    
    return len(errors) == 0, errors
