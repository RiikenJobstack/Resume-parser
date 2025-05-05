import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings"""
    # API settings
    API_TITLE = "Resume Parser API"
    API_VERSION = "1.0.0"
    
    # OpenAI settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_SIMPLE = os.getenv("OPENAI_MODEL_SIMPLE", "gpt-3.5-turbo")
    OPENAI_MODEL_COMPLEX = os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4-turbo-preview")
    
    # Redis settings
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    REDIS_TTL = int(os.getenv("REDIS_TTL", 86400))  # 24 hours
    
    # Application settings
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    
    # File size limits
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10 MB

settings = Settings()