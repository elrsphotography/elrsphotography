import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "elrs_photography_secret_key_2026")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/elrs_photography")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "elrs_photography")
    
    # Google Drive Service Account Configuration
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
    SERVICE_ACCOUNT_JSON_ENV = os.getenv("GOOGLE_CREDENTIALS_JSON", None) # Allows raw JSON string in Render ENV
    
    # In-memory Caching Configuration (Render Free Tier Friendly)
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 1800  # 30 minutes cache for Drive API folder listings

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True

config_by_name = {
    "dev": DevelopmentConfig,
    "prod": ProductionConfig
}