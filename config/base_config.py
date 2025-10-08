# config/base_config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application configuration with environment variable support"""
    
    # Application
    APP_NAME: str = "Bio-Data-Validation"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    
    # External APIs
    NCBI_API_KEY: Optional[str] = None
    ENSEMBL_API_URL: str = "https://rest.ensembl.org"
    
    # API Rate Limiting
    NCBI_BATCH_SIZE: int = 100
    NCBI_RATE_LIMIT_DELAY: float = 0.34  # Max 3 requests/second
    ENSEMBL_BATCH_SIZE: int = 50
    
    # MLFlow
    MLFLOW_TRACKING_URI: str
    MLFLOW_EXPERIMENT_NAME: str = "bio-validation"
    
    # Monitoring
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"
    
    # Orchestrator Configuration
    ORCHESTRATOR_TIMEOUT_SECONDS: int = 300
    ENABLE_SHORT_CIRCUIT: bool = True
    
    # Policy Engine
    POLICY_CONFIG_PATH: str = "config/policy_config.yml"
    VALIDATION_RULES_PATH: str = "config/validation_rules.yml"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()