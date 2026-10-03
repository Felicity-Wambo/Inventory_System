# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Inventory Management System"
    SECRET_KEY: str = "change-this-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database - switch to PostgreSQL by changing this URL
    # DATABASE_URL: str = "sqlite:///./inventory.db"
    DATABASE_URL: str = "postgresql://postgres:1515@localhost:5000/inventory"
    
    UPLOAD_DIR: str = "./uploads"
    REPORT_DIR: str = "./reports"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()