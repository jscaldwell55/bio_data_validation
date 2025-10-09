# config/base_config.py
"""
Application configuration with environment variable support.
Uses pydantic-settings for type-safe configuration management.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Application configuration with environment variable support.
    
    All settings can be overridden via environment variables or .env file.
    Example: APP_NAME="Custom Name" in .env
    """
    
    # =============================================================================
    # Application Settings
    # =============================================================================
    APP_NAME: str = "Bio-Data-Validation"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    
    # =============================================================================
    # Database Settings
    # =============================================================================
    # FIXED: Provide sensible default for development
    DATABASE_URL: str = "sqlite:///./bio_validation.db"
    # For production, override with:
    # DATABASE_URL=postgresql://user:pass@localhost/bio_validation
    
    # =============================================================================
    # External API Settings
    # =============================================================================
    # NCBI E-utilities
    NCBI_API_KEY: Optional[str] = None
    NCBI_BASE_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    NCBI_BATCH_SIZE: int = 50  # Reduced from 100 for optimal performance
    
    # FIXED: Rate limit depends on API key presence
    # With API key: 10 req/sec = 0.1 second delay
    # Without API key: 3 req/sec = 0.34 second delay
    # This will be dynamically set in BioLookupsValidator based on key presence
    NCBI_RATE_LIMIT_DELAY: float = 0.34  # Default (no API key)
    NCBI_MAX_RETRIES: int = 3
    NCBI_TIMEOUT: int = 30  # seconds
    
    # Ensembl REST API
    ENSEMBL_API_URL: str = "https://rest.ensembl.org"
    ENSEMBL_BATCH_SIZE: int = 50
    ENSEMBL_RATE_LIMIT_DELAY: float = 0.1
    ENSEMBL_TIMEOUT: int = 30  # seconds
    
    # =============================================================================
    # MLOps Settings
    # =============================================================================
    # MLflow
    MLFLOW_TRACKING_URI: str = "sqlite:///./mlruns.db"  # FIXED: Default for dev
    # For production, override with:
    # MLFLOW_TRACKING_URI=http://mlflow-server:5000
    MLFLOW_EXPERIMENT_NAME: str = "bio-validation"
    MLFLOW_ENABLE_TRACKING: bool = False  # Disable by default
    
    # Data Version Control (DVC)
    DVC_REMOTE_URL: Optional[str] = None
    DVC_CACHE_DIR: str = ".dvc/cache"
    
    # =============================================================================
    # Monitoring & Observability
    # =============================================================================
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE: Optional[str] = None  # None = stdout only
    
    # Prometheus metrics
    PROMETHEUS_ENABLED: bool = False  # Disabled by default for dev
    PROMETHEUS_PORT: int = 9090
    PROMETHEUS_PATH: str = "/metrics"
    
    # =============================================================================
    # Validation Orchestrator Settings
    # =============================================================================
    ORCHESTRATOR_TIMEOUT_SECONDS: int = 300  # 5 minutes
    ENABLE_SHORT_CIRCUIT: bool = True  # Stop on critical failures
    ENABLE_PARALLEL_BIO: bool = True  # Parallel bio validation
    
    # =============================================================================
    # Policy & Rules Configuration
    # =============================================================================
    POLICY_CONFIG_PATH: str = "config/policy_config.yml"
    VALIDATION_RULES_PATH: str = "config/validation_rules.yml"
    
    # =============================================================================
    # API Server Settings (if using FastAPI)
    # =============================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = False  # Auto-reload on code changes (dev only)
    
    # CORS settings
    CORS_ENABLED: bool = True
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # =============================================================================
    # Performance & Resource Limits
    # =============================================================================
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_RECORDS_PER_VALIDATION: int = 100000
    WORKER_POOL_SIZE: int = 4
    
    # =============================================================================
    # Security Settings
    # =============================================================================
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY_ENABLED: bool = False
    API_KEY_HEADER: str = "X-API-Key"
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Allow extra fields from environment
        extra = "ignore"
    
    def __init__(self, **kwargs):
        """Initialize settings with dynamic rate limit adjustment"""
        super().__init__(**kwargs)
        
        # ADDED: Dynamically adjust NCBI rate limit based on API key
        if self.NCBI_API_KEY:
            self.NCBI_RATE_LIMIT_DELAY = 0.1  # 10 req/sec with key
        else:
            self.NCBI_RATE_LIMIT_DELAY = 0.34  # 3 req/sec without key
    
    @property
    def ncbi_requests_per_second(self) -> int:
        """Calculate NCBI requests per second based on current rate limit"""
        return int(1.0 / self.NCBI_RATE_LIMIT_DELAY)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"
    
    def get_database_path(self) -> Optional[Path]:
        """Get database path if using SQLite"""
        if self.DATABASE_URL.startswith("sqlite:///"):
            return Path(self.DATABASE_URL.replace("sqlite:///", ""))
        return None


# Global settings instance
settings = Settings()


# =============================================================================
# Usage Examples
# =============================================================================
# 
# In your code:
# --------------
# from config.base_config import settings
# 
# # Access settings
# print(settings.NCBI_API_KEY)
# print(settings.DATABASE_URL)
# 
# # Check environment
# if settings.is_production:
#     # Production-specific logic
#     pass
# 
# In .env file:
# -------------
# # Override any setting
# ENVIRONMENT=production
# DATABASE_URL=postgresql://user:pass@localhost/bio_validation
# NCBI_API_KEY=your_actual_api_key_here
# LOG_LEVEL=WARNING
# MLFLOW_TRACKING_URI=http://mlflow-server:5000
# =============================================================================